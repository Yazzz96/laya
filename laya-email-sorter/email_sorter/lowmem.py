"""Load a laya checkpoint in bf16 with ~1x weight memory (for small-RAM machines)."""
import torch
import safetensors.torch as A

_orig_load_file = A.load_file


def _bf16_load_file(path, *a, **k):
    w = _orig_load_file(path, *a, **k)
    for key in list(w):
        if w[key].is_floating_point():
            w[key] = w[key].to(torch.bfloat16)
    return w


_orig_lsd = torch.nn.Module.load_state_dict


def _assign_lsd(self, sd, strict=True, assign=False):
    return _orig_lsd(self, sd, strict=strict, assign=True)


def enable():
    """Call before the first Router/Agent is built. CPU only."""
    import os
    os.environ.setdefault("LAYA_CPU_AMP", "bf16")
    torch.set_default_dtype(torch.bfloat16)
    A.load_file = _bf16_load_file
    torch.nn.Module.load_state_dict = _assign_lsd
