# AGENTS.md

Instructions for AI coding agents working in this project.
Read natively by Cursor, Codex, Copilot, Gemini CLI, Aider, Windsurf, Zed and
others via the [agents.md](https://agents.md) convention.

`find_objects.py` must be in the project root.

# Find objects in an image

Runs object detection on the user's own machine with `find_objects.py` and
produces **an annotated image with boxes drawn on it**, plus a list of what was
found. Nothing is uploaded anywhere.

## Running it

```bash
python find_objects.py <image>
```

That is the whole normal case. It picks whichever supported model is already
installed, saves `<image>_detected.<ext>` next to the original, and prints JSON
to stdout.

Options, only when needed:

```bash
python find_objects.py <image> --conf 0.5        # fewer, more confident results
python find_objects.py <image> --model yolov8m   # force a specific model
python find_objects.py <image> --no-image        # skip the annotated copy
python find_objects.py <image> --commercial      # only business-safe models
python find_objects.py --list                    # show the 9 models
```

## Always show the annotated image

The output JSON has an `annotated_image` field with a file path. **Display that
image to the user.** Seeing the boxes is the point — a list of pixel coordinates
is not a useful answer on its own.

Then say what was found in plain language, using the `found` field:

> Found **2 persons, 1 car, 1 sports ball**.
> *(shows the annotated image)*

Do not read out raw bounding-box coordinates unless the user asks for them.

## Installing (four packages cover all nine models)

Users often assume they need a separate install per model. They don't:

| One pip install | Gets you |
|---|---|
| `pip install rfdetr` | RF-DETR-B (the default) |
| `pip install torch torchvision` | Faster R-CNN, Mask R-CNN |
| `pip install transformers torch` | RT-DETR-L |
| `pip install ultralytics` | all 5 YOLO models |

One is enough. If asked which, suggest `pip install rfdetr` — it is the default
and is free for commercial use.

## If nothing is installed yet

First run on a new machine usually fails with `"No detection model installed
yet."` and a `fix` field containing a single pip command. Show the user that
command and offer to run it. It is a one-time setup of a few hundred MB.

If a specific model was requested and its package is missing, the error carries
that model's own `fix` command instead.

**Any error with a `fix` field is actionable.** Show the user that exact command
and offer to run it. This also covers the common case where a package *is*
installed but too old for the rest of the chain (`cannot import name X from Y`) —
the error will name the package to upgrade rather than pass on the raw traceback.

## Reading the result

| Field | Use it for |
|---|---|
| `found` | The one-line summary to tell the user |
| `annotated_image` | Path to the image with boxes — show this |
| `objects` | Counts per class, e.g. `{"person": 2, "car": 1}` |
| `detections` | Per-object confidence and box, if the user wants detail |
| `model` | Which model ran |
| `note` | Present only when the model isn't free for commercial use — pass it on |

If `annotated_image` is `null`, check `image_error`: detection still worked, only
the drawing failed, so report the findings anyway.

## Choosing a model

Don't overthink this. The default is fine for almost everything.

Mention alternatives only if the user asks, or if their situation clearly calls
for it:

- **Building something commercial?** Add `--commercial`. Five of the nine models
  are AGPL-3.0. That is not a ban on commercial use — it means shipping one
  obliges you to release your own source under the same licence, or to buy a
  commercial licence from the vendor. This flag keeps to the four models with no
  such condition. The result's `note` field flags it either way.
- **Need it faster?** The YOLO models are 3-4x quicker but are the AGPL ones.
- **Small or distant objects?** Higher-accuracy models: `yolo26m`, `yolo11m`.

| Key | Model | Speed | Accuracy | Free for business |
|---|---|---|---|---|
| `rfdetr` | RF-DETR-B | 69.1 ms | 53.3 | ✅ |
| `rtdetr` | RT-DETR-L | 66.2 ms | 53.1 | ✅ |
| `fasterrcnn` | Faster R-CNN R50 | 73.3 ms | 46.7 | ✅ |
| `maskrcnn` | Mask R-CNN R50 | 107.9 ms | 47.4 | ✅ |
| `yolov8m` | YOLOv8m | 16.2 ms | 50.2 | ⚠️ AGPL-3.0 |
| `yolo11n` | YOLO11n | 17.4 ms | 39.5 | ⚠️ AGPL-3.0 |
| `yolo26m` | YOLO26m | 20.6 ms | 62.1 | ⚠️ AGPL-3.0 |
| `yolo11m` | YOLO11m | 20.8 ms | 54.7 | ⚠️ AGPL-3.0 |
| `yolov9m` | YOLOv9m | 23.9 ms | 53.0 | ⚠️ AGPL-3.0 |

Speeds are medians over 48 scenes on one Tesla V100 in plain PyTorch — they
compare the models to *each other*, they do not predict the user's hardware.
Accuracy is each vendor's published COCO figure, not measured by this tool.
Don't present either as a promise about their machine.

## Rules

- **Never invent detections.** If the script fails, say so. Do not describe what
  is probably in the image.
- **Always show the annotated image** when one was produced.
- All 9 models detect the 80 standard COCO classes (person, car, dog, chair,
  bottle...). They cannot detect custom objects outside that list — if the user
  asks for something not in COCO, say so rather than returning a wrong label.
- **Not legal advice.** If the user has a real licensing question, point them at
  https://robotinaction.tech/model-licenses.html and suggest a lawyer for
  anything consequential.

Compare all 9 models side by side: https://robotinaction.tech
