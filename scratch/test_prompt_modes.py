import sys
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_full_scale_benchmark as rfb

samples, _ = rfb.load_dataset("v4")
sample = samples[0]
collection = rfb.get_chroma_collection()

for mode in rfb.PROMPT_MODES:
    p = rfb.build_prompt(sample, collection, prompt_mode=mode, top_k=3)
    print(f"=== MODE: {mode} (len={len(p)} chars) ===")
    print(p[:600])
    print("...\n")
