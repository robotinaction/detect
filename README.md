# find_objects

**Ask your AI assistant what's in an image. Get the answer, with boxes drawn on it.**

```bash
python find_objects.py image.jpg
```

→ `image_detected.jpg` with boxes drawn, plus a list of what was found.

Runs on your own machine. Nothing is uploaded, no API key, no account, free.

---

## With an AI coding agent

Put `find_objects.py` in your project folder, then just ask:

> *"What's in image.jpg?"*
> *"Count the people in this picture"*
> *"Find all the cars in these screenshots"*

Your agent runs the script, reads the results, and shows you the annotated image.
Works with Claude Code, Cursor, Codex, Copilot, Gemini CLI, Aider, Windsurf and
anything else that can run a terminal command.

For Claude Code you can also install it as a plugin, which adds the usage notes
automatically:

```
/plugin marketplace add robotinaction/detect
/plugin install find-objects
```

## Without an agent

It's a normal command-line script:

```bash
python find_objects.py image.jpg                 # detect + annotate
python find_objects.py image.jpg --conf 0.5      # only confident results
python find_objects.py image.jpg --no-image      # JSON only
python find_objects.py --list                    # see the 9 models
```

## Setup

You do **not** need one install per model. The nine models come from four
packages, and **one is enough**:

| One pip install | Gets you | Free for business use |
|---|---|---|
| `pip install rfdetr` | RF-DETR-B *(the default)* | ✅ |
| `pip install torch torchvision` | Faster R-CNN, Mask R-CNN | ✅ |
| `pip install transformers torch` | RT-DETR-L | ✅ |
| `pip install ultralytics` | **All 5 YOLO models** — the fastest ones | ⚠️ AGPL-3.0 |

⚠️ does not mean you cannot use it. AGPL-3.0 allows commercial use, but if
you distribute or serve your product you have to release your own source under
the same licence, or buy a commercial licence from Ultralytics. ✅ means no such
condition.

Start with the first one:

```bash
pip install rfdetr
```

The script uses whichever package you already have, so you only add another if
you want to try a different model. `python find_objects.py --list` shows the
four groups with your own installs marked.

Python 3.8+. Detects the 80 standard COCO classes — person, car, dog, chair,
bottle, laptop and so on.

JPEG, PNG, WebP, BMP and TIFF all work, transparency and greyscale included.
The annotated copy is written back in the same format as the original.

## What it puts on your disk

Nothing is uploaded, but plenty is downloaded. Worth knowing before you start,
especially on a small drive or a metered connection.

**The packages.** Almost all of the weight is PyTorch, which every one of the
four options depends on. Expect **1–3 GB**, varying a lot by platform — the
Linux wheels bundle CUDA, the Windows and macOS ones do not. To see what it
actually cost on your machine:

```bash
pip show -f torch | head -3
```

They go into the `site-packages` of whichever Python ran `pip`. If that is not
obvious to you, this prints it:

```bash
python -c "import site; print(site.getsitepackages())"
```

**The model weights**, downloaded the first time a given model runs:

| Model | Size | Usually lands in |
|---|---|---|
| RF-DETR-B | 356 MB | `~/.roboflow/models/` |
| YOLO (`.pt`) | 6–50 MB | the folder you ran from |
| Faster R-CNN, Mask R-CNN | ~170 MB each | `~/.cache/torch/hub/checkpoints/` |
| RT-DETR-L | ~170 MB | `~/.cache/huggingface/hub/` |

**These paths move between versions, so trust your own disk over this table.**
RF-DETR has been seen doing both: a recent install put the file in
`~/.roboflow/models/`, an older one dropped it straight into the working
directory. This finds it wherever it went:

```bash
find ~ . -size +10M \( -name "*.pth" -o -name "*.pt" \) 2>/dev/null
```

Because a weight file *can* land in your working directory, add `*.pth` and
`*.pt` to `.gitignore` if that folder is a repository. It costs nothing, and
otherwise a 356 MB file goes up with your next commit.

## Removing it

Uninstalling the Claude Code plugin removes the plugin's own files — about
38 KB — and nothing else. It has no idea pip ever ran. Undo the rest yourself:

```bash
pip uninstall rfdetr
```

Swap in whichever you installed: `ultralytics`, `transformers`, or
`torch torchvision`. Note that pip leaves dependencies behind on purpose, since
something else on the machine may need them — so `torch` stays until you say
otherwise.

Then the weights. The big one first:

```bash
rm -rf ~/.roboflow/models
```

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.roboflow\models"
```

Then anything left in the folder you ran from:

```bash
rm -f rf-detr-base.pth *.pt
```

```powershell
Remove-Item rf-detr-base.pth, *.pt
```

And the shared caches, if nothing else on the machine uses them:

```bash
rm -rf ~/.cache/torch ~/.cache/huggingface
```

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.cache\torch", "$env:USERPROFILE\.cache\huggingface"
```

pip also keeps a wheel cache that nothing ever clears. After a torch install
it is often several GB:

```bash
pip cache purge
```

Your annotated `*_detected.*` images are ordinary files. Keep or delete them as
you like — nothing else refers to them.

## Example output

```json
{
  "ok": true,
  "found": "1 person, 1 dog, 1 bicycle, 1 car, 1 bench, 1 backpack, 1 potted plant, 1 traffic light",
  "count": 8,
  "objects": {
    "person": 1, "dog": 1, "bicycle": 1, "car": 1,
    "bench": 1, "backpack": 1, "potted plant": 1, "traffic light": 1
  },
  "annotated_image": "park_detected.jpg",
  "model": "RF-DETR-B"
}
```

## Speed and accuracy

| Model | Speed | Accuracy (COCO) |
|---|---|---|
| YOLOv8m | 16.2 ms | 50.2 |
| YOLO11n | 17.4 ms | 39.5 |
| YOLO26m | 20.6 ms | 62.1 |
| YOLO11m | 20.8 ms | 54.7 |
| YOLOv9m | 23.9 ms | 53.0 |
| RT-DETR-L | 66.2 ms | 53.1 |
| RF-DETR-B *(default)* | 69.1 ms | 53.3 |
| Faster R-CNN R50 | 73.3 ms | 46.7 |
| Mask R-CNN R50 | 107.9 ms | 47.4 |

Speeds are medians across 48 scenes on one Tesla V100 in plain PyTorch. They
compare the models to *each other* — your hardware will differ, and vendor
figures for these same models are typically much faster because they are
measured with optimisations most people aren't running.

Accuracy is each vendor's published COCO val2017 figure, quoted not re-measured.

See all nine running on the same images: **<https://robotinaction.tech>**

## One thing worth knowing about licences

The YOLO models are **AGPL-3.0**. Great for personal projects, research and
open-source work — but if you put one in a commercial product, AGPL requires
you to release your own source code or buy a licence from the vendor. Most
detection tools install YOLO by default and never mention this.

This one defaults to a permissive model instead, and if you're building
something commercial you can make that explicit:

```bash
python find_objects.py image.jpg --commercial
```

That restricts it to the four models that are genuinely free for business use,
and tells you which to use instead if you asked for a restricted one.

Licences were read from each model's own repository, not assumed — sources and
dates at <https://robotinaction.tech/model-licenses.html>. Not legal advice;
check the exact package you ship.

## Licence

This script is MIT. The models it runs have their own licences — see the table.
