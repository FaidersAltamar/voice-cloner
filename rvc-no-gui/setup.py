"""
RVC Setup and Installation Module
Handles cloning RVC repository, downloading pretrained models, and installing dependencies.
"""
import os
import subprocess
import shutil
import sys
from pathlib import Path
from typing import Optional
import logging

from config import PipelineConfig, PathConfig, PretrainedConfig, PLATFORM

logger = logging.getLogger(__name__)


class RVCSetup:
    """Handles RVC environment setup and installation."""

    RVC_REPO_URL = "https://github.com/nakshatra-garg/rvc-deps"

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.paths = config.paths
        self.pretrained = config.pretrained

    def setup_all(self, force_reinstall: bool = False) -> bool:
        """
        Run complete setup process.

        Args:
            force_reinstall: If True, remove existing installation and reinstall

        Returns:
            True if setup completed successfully
        """
        logger.info("Starting RVC setup...")

        # Check required tools
        if not PLATFORM.has_git:
            logger.error("Git is not installed. Please install Git first.")
            logger.error("  Ubuntu/Debian: sudo apt install git")
            logger.error("  Windows: https://git-scm.com/download/win")
            return False

        if not PLATFORM.has_ffmpeg:
            logger.warning("FFmpeg not found. Some audio operations may fail.")
            logger.warning("  Ubuntu/Debian: sudo apt install ffmpeg")
            logger.warning("  Windows: https://ffmpeg.org/download.html")

        if not PLATFORM.has_aria2c:
            logger.info("aria2c not found, will use slower urllib for downloads")

        # Create directories
        self.paths.ensure_directories()

        # Clone RVC repository
        if not self._clone_rvc_repo(force=force_reinstall):
            return False

        # Patch RVC for PyTorch 2.6+ compatibility
        self._patch_torch_load_compatibility()

        # Download pretrained models
        if not self._download_pretrained_models():
            return False

        # Download additional files
        if not self._download_additional_files():
            return False

        # Install Python dependencies
        if not self._install_dependencies():
            return False

        # Patch fairseq and hydra for Python 3.11 dataclass compatibility
        self._patch_fairseq_py311()
        self._patch_hydra_py311()

        logger.info("RVC setup completed successfully!")
        return True

    def _patch_torch_load_compatibility(self):
        """
        Patch RVC files for PyTorch 2.6+ compatibility.
        PyTorch 2.6 changed torch.load to use weights_only=True by default,
        which breaks loading fairseq/hubert models.
        """
        logger.info("Patching RVC for PyTorch 2.6+ compatibility...")

        rvc_dir = self.paths.rvc_dir

        # Files that need patching for torch.load
        files_to_patch = [
            rvc_dir / "infer" / "modules" / "train" / "extract_feature_print.py",
            rvc_dir / "infer" / "lib" / "rmvpe.py",
            rvc_dir / "infer" / "modules" / "vc" / "modules.py",
            rvc_dir / "infer" / "modules" / "train" / "train.py",
        ]

        # Fix matplotlib compatibility in utils.py (tostring_rgb -> buffer_rgba)
        utils_file = rvc_dir / "infer" / "lib" / "train" / "utils.py"
        if utils_file.exists():
            try:
                content = utils_file.read_text(encoding='utf-8')
                if 'tostring_rgb' in content:
                    # Simple line replacement for matplotlib 3.8+ compatibility
                    content = content.replace(
                        'data = np.fromstring(fig.canvas.tostring_rgb(), dtype=np.uint8, sep="")',
                        'data = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]'
                    )
                    content = content.replace(
                        'data = data.reshape(fig.canvas.get_width_height()[::-1] + (3,))',
                        '# data already in correct shape from buffer_rgba'
                    )
                    utils_file.write_text(content, encoding='utf-8')
                    logger.info("  Patched: utils.py (matplotlib compatibility)")
            except Exception as e:
                logger.warning(f"  Failed to patch utils.py: {e}")

        for filepath in files_to_patch:
            if not filepath.exists():
                continue

            try:
                content = filepath.read_text(encoding='utf-8')
                original_content = content

                # Pattern 1: torch.load(xxx) -> torch.load(xxx, weights_only=False)
                # But avoid double-patching if already has weights_only
                import re

                # Find torch.load calls that don't already have weights_only
                # This regex finds torch.load(...) that doesn't contain weights_only
                def patch_torch_load(match):
                    full_match = match.group(0)
                    if 'weights_only' in full_match:
                        return full_match  # Already patched
                    # Insert weights_only=False before the closing paren
                    return full_match[:-1] + ', weights_only=False)'

                # Match torch.load(...) calls - simple cases
                content = re.sub(
                    r'torch\.load\([^)]+\)',
                    patch_torch_load,
                    content
                )

                if content != original_content:
                    filepath.write_text(content, encoding='utf-8')
                    logger.info(f"  Patched: {filepath.name}")

            except Exception as e:
                logger.warning(f"  Failed to patch {filepath.name}: {e}")

        # Also patch fairseq if installed (common issue)
        try:
            import fairseq
            fairseq_path = Path(fairseq.__file__).parent / "checkpoint_utils.py"
            if fairseq_path.exists():
                content = fairseq_path.read_text(encoding='utf-8')
                if 'weights_only=False' not in content:
                    # Add weights_only=False to the torch.load call
                    content = content.replace(
                        'torch.load(f, map_location=torch.device("cpu"))',
                        'torch.load(f, map_location=torch.device("cpu"), weights_only=False)'
                    )
                    fairseq_path.write_text(content, encoding='utf-8')
                    logger.info("  Patched: fairseq/checkpoint_utils.py")
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"  Could not patch fairseq: {e}")

        logger.info("Patching complete")

    def _patch_fairseq_py311(self) -> None:
        """Patch fairseq dataclass configs for Python 3.11 (mutable default not allowed)."""
        if sys.version_info < (3, 11):
            return
        try:
            # Find fairseq without importing (import triggers the error)
            import site
            for sp in [site.getusersitepackages()] + site.getsitepackages():
                configs_file = Path(sp) / "fairseq" / "dataclass" / "configs.py"
                if configs_file.exists():
                    break
            else:
                return
            content = configs_file.read_text(encoding="utf-8")
            if "default_factory=CommonConfig" in content:
                return  # Already patched
            # Replace mutable defaults with field(default_factory=...)
            replacements = [
                ("common: CommonConfig = CommonConfig()", "common: CommonConfig = field(default_factory=CommonConfig)"),
                ("common_eval: CommonEvalConfig = CommonEvalConfig()", "common_eval: CommonEvalConfig = field(default_factory=CommonEvalConfig)"),
                ("distributed_training: DistributedTrainingConfig = DistributedTrainingConfig()", "distributed_training: DistributedTrainingConfig = field(default_factory=DistributedTrainingConfig)"),
                ("dataset: DatasetConfig = DatasetConfig()", "dataset: DatasetConfig = field(default_factory=DatasetConfig)"),
                ("optimization: OptimizationConfig = OptimizationConfig()", "optimization: OptimizationConfig = field(default_factory=OptimizationConfig)"),
                ("checkpoint: CheckpointConfig = CheckpointConfig()", "checkpoint: CheckpointConfig = field(default_factory=CheckpointConfig)"),
                ("bmuf: FairseqBMUFConfig = FairseqBMUFConfig()", "bmuf: FairseqBMUFConfig = field(default_factory=FairseqBMUFConfig)"),
                ("generation: GenerationConfig = GenerationConfig()", "generation: GenerationConfig = field(default_factory=GenerationConfig)"),
                ("eval_lm: EvalLMConfig = EvalLMConfig()", "eval_lm: EvalLMConfig = field(default_factory=EvalLMConfig)"),
                ("interactive: InteractiveConfig = InteractiveConfig()", "interactive: InteractiveConfig = field(default_factory=InteractiveConfig)"),
                ("ema: EMAConfig = EMAConfig()", "ema: EMAConfig = field(default_factory=EMAConfig)"),
            ]
            for old, new in replacements:
                content = content.replace(old, new)
            configs_file.write_text(content, encoding="utf-8")
            logger.info("Patched fairseq configs for Python 3.11 dataclass compatibility")

            # Patch transformer_config.py (loaded by fairseq.models)
            trans_cfg = configs_file.parent.parent / "models" / "transformer" / "transformer_config.py"
            if trans_cfg.exists():
                tc = trans_cfg.read_text(encoding="utf-8")
                if "field(default_factory=EncDecBaseConfig)" not in tc:
                    tc = tc.replace("encoder: EncDecBaseConfig = EncDecBaseConfig()", "encoder: EncDecBaseConfig = field(default_factory=EncDecBaseConfig)")
                    tc = tc.replace("decoder: DecoderConfig = DecoderConfig()", "decoder: DecoderConfig = field(default_factory=DecoderConfig)")
                    tc = tc.replace("quant_noise: QuantNoiseConfig = field(default=QuantNoiseConfig())", "quant_noise: QuantNoiseConfig = field(default_factory=QuantNoiseConfig)")
                    trans_cfg.write_text(tc, encoding="utf-8")
                    logger.info("Patched fairseq transformer_config for Python 3.11")
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Could not patch fairseq for Python 3.11: {e}")

        # Also patch fairseq hydra_init to handle default_factory and skip MISSING
        try:
            init_file = configs_file.parent / "initialize.py"
            if init_file.exists():
                init_content = init_file.read_text(encoding="utf-8")
                if "default_factory" in init_content and "fields(FairseqConfig)" in init_content:
                    pass  # Already patched
                elif "for k in FairseqConfig.__dataclass_fields__:" in init_content:
                    old_block = """    for k in FairseqConfig.__dataclass_fields__:
        v = FairseqConfig.__dataclass_fields__[k].default
        try:
            cs.store(name=k, node=v)
        except BaseException:
            logger.error(f"{k} - {v}")
            raise"""
                    new_block = """    from dataclasses import fields, MISSING
    for f in fields(FairseqConfig):
        if f.default is not MISSING:
            v = f.default
        elif f.default_factory is not MISSING:
            v = f.default_factory()
        else:
            continue
        try:
            cs.store(name=f.name, node=v)
        except BaseException:
            logger.error(f"{f.name} - {v}")
            raise"""
                    init_content = init_content.replace(old_block, new_block)
                    init_file.write_text(init_content, encoding="utf-8")
                    logger.info("Patched fairseq hydra_init for Python 3.11")
        except Exception as e:
            logger.warning(f"Could not patch fairseq initialize: {e}")

    def _patch_hydra_py311(self) -> None:
        """Patch hydra dataclass configs for Python 3.11 (mutable default not allowed)."""
        if sys.version_info < (3, 11):
            return
        try:
            import site
            for sp in [site.getusersitepackages()] + site.getsitepackages():
                hydra_conf = Path(sp) / "hydra" / "conf" / "__init__.py"
                if hydra_conf.exists():
                    break
            else:
                return
            content = hydra_conf.read_text(encoding="utf-8")
            if "default_factory=OverrideDirname" in content:
                return  # Already patched
            replacements = [
                ("override_dirname: OverrideDirname = OverrideDirname()", "override_dirname: OverrideDirname = field(default_factory=OverrideDirname)"),
                ("config: JobConfig = JobConfig()", "config: JobConfig = field(default_factory=JobConfig)"),
                ("run: RunDir = RunDir()", "run: RunDir = field(default_factory=RunDir)"),
                ("sweep: SweepDir = SweepDir()", "sweep: SweepDir = field(default_factory=SweepDir)"),
                ("help: HelpConf = HelpConf()", "help: HelpConf = field(default_factory=HelpConf)"),
                ("hydra_help: HydraHelpConf = HydraHelpConf()", "hydra_help: HydraHelpConf = field(default_factory=HydraHelpConf)"),
                ("overrides: OverridesConf = OverridesConf()", "overrides: OverridesConf = field(default_factory=OverridesConf)"),
                ("job: JobConf = JobConf()", "job: JobConf = field(default_factory=JobConf)"),
                ("runtime: RuntimeConf = RuntimeConf()", "runtime: RuntimeConf = field(default_factory=RuntimeConf)"),
            ]
            for old, new in replacements:
                content = content.replace(old, new)
            hydra_conf.write_text(content, encoding="utf-8")
            logger.info("Patched hydra for Python 3.11 dataclass compatibility")
        except Exception as e:
            logger.warning(f"Could not patch hydra for Python 3.11: {e}")

    def _is_valid_rvc_repo(self, rvc_dir: Path) -> bool:
        """Check if the RVC directory contains a valid clone."""
        required_files = [
            "requirements.txt",
            "infer/modules/train/train.py",
        ]
        required_dirs = [
            "infer",
            "configs",
        ]

        for f in required_files:
            if not (rvc_dir / f).exists():
                return False
        for d in required_dirs:
            if not (rvc_dir / d).is_dir():
                return False
        return True

    def _clone_rvc_repo(self, force: bool = False) -> bool:
        """Clone the RVC repository."""
        rvc_dir = self.paths.rvc_dir

        if rvc_dir.exists():
            if force:
                logger.info(f"Removing existing RVC directory: {rvc_dir}")
                shutil.rmtree(rvc_dir)
            elif self._is_valid_rvc_repo(rvc_dir):
                logger.info(f"RVC directory already exists and is valid: {rvc_dir}")
                return True
            else:
                logger.warning(f"RVC directory exists but is incomplete/invalid. Re-cloning...")
                shutil.rmtree(rvc_dir)

        logger.info(f"Cloning RVC repository to {rvc_dir}...")
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", self.RVC_REPO_URL, str(rvc_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("RVC repository cloned successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone RVC repository: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("Git is not installed. Please install Git first.")
            return False

    def _download_pretrained_models(self) -> bool:
        """Download pretrained models using aria2c or urllib."""
        pretrained_dir = self.paths.pretrained_dir
        pretrained_dir.mkdir(parents=True, exist_ok=True)

        # Download standard pretrained models
        for filename in self.pretrained.standard_pretrains:
            filepath = pretrained_dir / filename
            if not filepath.exists():
                url = f"{self.pretrained.standard_base_url}/{filename}"
                if not self._download_file(url, filepath):
                    logger.warning(f"Failed to download {filename}")

        # Download OV2 Super pretrained models
        for filename in self.pretrained.ov2_pretrains:
            filepath = pretrained_dir / filename
            if not filepath.exists():
                url = f"{self.pretrained.ov2_base_url}/{filename}"
                if not self._download_file(url, filepath):
                    logger.warning(f"Failed to download {filename}")

        return True

    def _download_file(self, url: str, filepath: Path) -> bool:
        """Download a file using aria2c (fast) or urllib (fallback)."""
        logger.info(f"Downloading {filepath.name}...")

        # Try aria2c first (faster, supports resuming)
        if self._try_aria2c_download(url, filepath):
            return True

        # Fallback to urllib
        return self._try_urllib_download(url, filepath)

    def _try_aria2c_download(self, url: str, filepath: Path) -> bool:
        """Try downloading with aria2c."""
        try:
            result = subprocess.run(
                [
                    "aria2c",
                    "--console-log-level=error",
                    "-c",  # Continue downloading
                    "-x", "16",  # Max connections per server
                    "-s", "16",  # Split file into parts
                    "-k", "1M",  # Min split size
                    url,
                    "-d", str(filepath.parent),
                    "-o", filepath.name
                ],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Downloaded {filepath.name} successfully")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _try_urllib_download(self, url: str, filepath: Path) -> bool:
        """Download using urllib."""
        import urllib.request
        try:
            urllib.request.urlretrieve(url, filepath)
            logger.info(f"Downloaded {filepath.name} successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to download {filepath.name}: {e}")
            return False

    def _download_additional_files(self) -> bool:
        """Download additional required files."""
        rvc_dir = self.paths.rvc_dir

        # Base URL for RVC models on HuggingFace
        hf_base_url = "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main"

        # Required model files for training
        model_files = [
            # RMVPE model for F0 extraction
            (f"{hf_base_url}/rmvpe.pt",
             rvc_dir / "assets" / "rmvpe" / "rmvpe.pt"),

            # Hubert model for feature extraction
            (f"{hf_base_url}/hubert_base.pt",
             rvc_dir / "assets" / "hubert" / "hubert_base.pt"),
        ]

        # Additional utility files
        additional_files = [
            ("https://raw.githubusercontent.com/RejektsAI/EasyTools/main/easyfuncs.py",
             rvc_dir / "easyfuncs.py"),
        ]

        all_files = model_files + additional_files

        for url, filepath in all_files:
            if not filepath.exists():
                # Ensure parent directory exists
                filepath.parent.mkdir(parents=True, exist_ok=True)
                if not self._download_file(url, filepath):
                    logger.error(f"Failed to download required file: {filepath.name}")
                    # rmvpe and hubert are critical - fail if they can't be downloaded
                    if "rmvpe" in str(filepath) or "hubert" in str(filepath):
                        return False

        return True

    def _get_requirements_file(self) -> Optional[Path]:
        """Get the appropriate requirements file. Python 3.11+ uses patched requirements.txt."""
        rvc_dir = self.paths.rvc_dir
        default_file = rvc_dir / "requirements.txt"

        if default_file.exists():
            if sys.version_info >= (3, 11):
                self._patch_requirements_for_py311(default_file)
            return default_file
        return None

    def _ensure_pip_for_fairseq(self) -> None:
        """Downgrade pip to <24.1 if needed for omegaconf/fairseq (pip 24.1+ rejects omegaconf 2.0.x)."""
        try:
            import pip
            pip_version = tuple(int(x) for x in pip.__version__.split(".")[:2])
            if pip_version >= (24, 1):
                logger.info("Downgrading pip for fairseq/omegaconf compatibility...")
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "pip==23.3.2", "-q"],
                    check=True, capture_output=True
                )
        except Exception as e:
            logger.warning(f"Could not adjust pip version: {e}")

    def _patch_requirements_for_py311(self, requirements_file: Path) -> None:
        """Patch requirements.txt for Python 3.11 compatibility (numba, llvmlite, pyworld)."""
        try:
            content = requirements_file.read_text(encoding="utf-8")
            original = content
            content = content.replace("numba==0.56.4", "numba>=0.57.0")
            content = content.replace("llvmlite==0.39.0", "llvmlite>=0.40.0")
            # pyworld 0.3.2 no tiene wheel para Python 3.11 en Windows; usar pyworld-prebuilt
            if sys.platform == "win32" and "pyworld==" in content:
                content = content.replace("pyworld==0.3.2", "pyworld-prebuilt>=0.3.0")
                logger.info("Patched pyworld -> pyworld-prebuilt (no C++ build needed)")
            if content != original:
                requirements_file.write_text(content, encoding="utf-8")
                logger.info("Patched requirements.txt for Python 3.11 compatibility")
        except Exception as e:
            logger.warning(f"Could not patch requirements for Python 3.11: {e}")

    def _install_dependencies(self) -> bool:
        """Install Python dependencies."""
        requirements_file = self._get_requirements_file()

        if requirements_file is None or not requirements_file.exists():
            logger.warning("requirements.txt not found in RVC directory")
            return True

        # pip 24.1+ rejects omegaconf 2.0.x (required by fairseq); downgrade if needed
        self._ensure_pip_for_fairseq()

        logger.info("Installing Python dependencies...")
        pip_args = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        # On Windows, --user can avoid "Acceso denegado" when DLLs are locked by other processes
        if sys.platform == "win32":
            pip_args.append("--user")
        addl_args = ["librosa", "soundfile", "pydub", "faiss-cpu"]
        try:
            subprocess.run(pip_args, check=True)
            addl_pip = [sys.executable, "-m", "pip", "install"] + addl_args
            if sys.platform == "win32":
                addl_pip.append("--user")
            subprocess.run(addl_pip, check=True)

            logger.info("Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e}")
            return False

    def verify_installation(self) -> bool:
        """Verify that RVC is properly installed."""
        checks = [
            (self.paths.rvc_dir.exists(), "RVC directory exists"),
            (self.paths.pretrained_dir.exists(), "Pretrained directory exists"),
            ((self.paths.pretrained_dir / "f0G32k.pth").exists(), "Standard pretrained models exist"),
        ]

        all_passed = True
        for check, description in checks:
            status = "OK" if check else "FAILED"
            logger.info(f"  [{status}] {description}")
            if not check:
                all_passed = False

        return all_passed


def setup_rvc(config: Optional[PipelineConfig] = None, force: bool = False) -> bool:
    """
    Convenience function to setup RVC.

    Args:
        config: Pipeline configuration (uses default if None)
        force: Force reinstallation

    Returns:
        True if setup successful
    """
    if config is None:
        config = PipelineConfig()

    setup = RVCSetup(config)
    return setup.setup_all(force_reinstall=force)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    config = PipelineConfig()
    setup_rvc(config)
