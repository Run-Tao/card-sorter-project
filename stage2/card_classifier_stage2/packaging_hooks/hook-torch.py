# Minimal PyInstaller hook for torch.
# The stock hook recursively collects every torch submodule, which dies in a
# subprocess on this Python 3.13 / torch 2.13 combination.  Our app only needs
# the core runtime plus the modules used by model_cnn.py.
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

binaries = collect_dynamic_libs("torch")
datas = collect_data_files("torch")
hiddenimports = [
    "torch", "torch.nn", "torch.nn.functional", "torch.nn.modules",
    "torch.optim", "torch.utils", "torch.utils.data", "torch.serialization",
    "torch.autograd", "torch.cuda", "torch.backends",
    "torch.backends.cudnn", "torch.backends.mkldnn",
]
