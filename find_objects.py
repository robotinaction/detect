#!/usr/bin/env python3
"""
find_objects.py - find objects in an image, and save a copy with boxes drawn on it.

    python find_objects.py photo.jpg

That's it. You get photo_detected.jpg with boxes drawn, plus the list of what
was found. Everything runs on your own machine - no upload, no API key, no
account.

More options:
    python find_objects.py photo.jpg --model yolov8m   # pick a specific model
    python find_objects.py photo.jpg --conf 0.5        # only confident hits
    python find_objects.py photo.jpg --no-image        # skip the output image
    python find_objects.py --list                      # show all 9 models

By default it picks whichever supported model you already have installed. If
you have none, it tells you the one pip command to run.

From RobotInAction - https://robotinaction.tech
"""

import argparse
import json
import os
import re
import sys

# Ships to other people's machines, so it must not die on their console.
# Em-dashes and similar encode on cp1252 but not cp932/cp866/ASCII.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

__version__ = "0.2.0"
SITE = "https://robotinaction.tech"

# --------------------------------------------------------------------------
# The models. `free_for_business` is shown in the output so you are not
# surprised later; it does not get in your way unless you ask it to
# (see --commercial). Speeds are our own medians over 48 scenes on one
# Tesla V100 in plain PyTorch - use them to compare models to each other,
# not to predict your hardware. Details: https://robotinaction.tech
# --------------------------------------------------------------------------
MODELS = {
    "rfdetr":     {"name": "RF-DETR-B",        "backend": "rfdetr",
                   "licence": "Apache-2.0",   "free_for_business": True,
                   "ms": 69.1, "map": 53.3, "pip": "pip install rfdetr"},
    "rtdetr":     {"name": "RT-DETR-L",        "backend": "rtdetr",
                   "licence": "Apache-2.0",   "free_for_business": True,
                   "ms": 66.2, "map": 53.1, "pip": "pip install transformers torch"},
    "fasterrcnn": {"name": "Faster R-CNN R50", "backend": "torchvision",
                   "licence": "BSD-3-Clause", "free_for_business": True,
                   "ms": 73.3, "map": 46.7, "pip": "pip install torch torchvision"},
    "maskrcnn":   {"name": "Mask R-CNN R50",   "backend": "torchvision",
                   "licence": "BSD-3-Clause", "free_for_business": True,
                   "ms": 107.9, "map": 47.4, "pip": "pip install torch torchvision"},
    "yolov8m":    {"name": "YOLOv8m",  "backend": "ultralytics", "weights": "yolov8m.pt",
                   "licence": "AGPL-3.0", "free_for_business": False,
                   "ms": 16.2, "map": 50.2, "pip": "pip install ultralytics"},
    "yolov9m":    {"name": "YOLOv9m",  "backend": "ultralytics", "weights": "yolov9m.pt",
                   "licence": "AGPL-3.0", "free_for_business": False,
                   "ms": 23.9, "map": 53.0, "pip": "pip install ultralytics"},
    "yolo11n":    {"name": "YOLO11n",  "backend": "ultralytics", "weights": "yolo11n.pt",
                   "licence": "AGPL-3.0", "free_for_business": False,
                   "ms": 17.4, "map": 39.5, "pip": "pip install ultralytics"},
    "yolo11m":    {"name": "YOLO11m",  "backend": "ultralytics", "weights": "yolo11m.pt",
                   "licence": "AGPL-3.0", "free_for_business": False,
                   "ms": 20.8, "map": 54.7, "pip": "pip install ultralytics"},
    "yolo26m":    {"name": "YOLO26m",  "backend": "ultralytics", "weights": "yolo26m.pt",
                   "licence": "AGPL-3.0", "free_for_business": False,
                   "ms": 20.6, "map": 62.1, "pip": "pip install ultralytics"},
}

# Order tried by "auto": models that are free for business first, so the
# default never quietly lands you on a licence you did not choose.
AUTO_ORDER = ["rfdetr", "rtdetr", "fasterrcnn", "maskrcnn",
              "yolov8m", "yolo11m", "yolo26m", "yolo11n", "yolov9m"]


def backend_available(backend):
    import importlib.util
    needed = {"rfdetr": "rfdetr", "rtdetr": "transformers",
              "torchvision": "torchvision", "ultralytics": "ultralytics"}[backend]
    return importlib.util.find_spec(needed) is not None


def pick_auto():
    """First installed model, business-friendly ones first. None if nothing installed."""
    for key in AUTO_ORDER:
        if backend_available(MODELS[key]["backend"]):
            return key
    return None


# --------------------------------------------------------------------------
# Drawing - the whole point is that you SEE the result, so this is on by
# default. Uses Pillow, which every backend below already pulls in.
# --------------------------------------------------------------------------
# Deep, saturated colours. The pastel set this replaced disappeared against
# pale backgrounds - a white wall, snow, an overexposed sky - which is exactly
# where a lot of photos live.
PALETTE = [(228, 37, 58), (0, 132, 222), (0, 163, 96), (232, 143, 0),
           (140, 66, 214), (222, 47, 141), (0, 158, 168), (206, 92, 24)]


def _text_on(colour):
    """Black or white, whichever stays readable on this fill."""
    r, g, b = colour
    return (15, 15, 20) if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else (255, 255, 255)


def _load_font(size):
    from PIL import ImageFont
    # Bold first. The label has to survive being viewed at thumbnail size, and
    # a regular weight at this size reads as grey rather than as text.
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "Helvetica-Bold.ttf",
                 "LiberationSans-Bold.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:  # noqa: BLE001 - font simply absent on this machine
            continue
    try:
        return ImageFont.load_default(size)  # Pillow >= 10.1
    except Exception:  # noqa: BLE001 - older Pillow, fixed-size bitmap font
        return ImageFont.load_default()


def _text_box(draw, text, font):
    try:
        return draw.textbbox((0, 0), text, font=font)
    except Exception:  # noqa: BLE001 - Pillow < 8.0
        w, h = draw.textsize(text, font=font)
        return 0, 0, w, h


def _hits(a, b):
    """Do two (left, top, right, bottom) rectangles overlap at all?"""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def draw_boxes(image_path, detections, out_path):
    from PIL import Image, ImageDraw
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Everything scales with the image, so a phone photo and a screenshot both
    # come out readable. Sized off the mean of the two dimensions rather than
    # the width alone - keying to width made labels tiny on portrait photos and
    # enormous on panoramas.
    scale = (img.width + img.height) / 2
    line = max(3, round(scale * 0.005))
    size = max(16, round(scale * 0.040))

    font = _load_font(size)
    pad = max(4, size // 5)
    labels = sorted({d["object"] for d in detections})

    # Two passes on purpose: every box first, then every label. Drawn in one
    # pass, a box belonging to a later detection gets painted straight across
    # the label of an earlier one, which is common whenever objects overlap.
    for d in detections:
        x1, y1, x2, y2 = d["box"]
        colour = PALETTE[labels.index(d["object"]) % len(PALETTE)]
        # A dark rule just outside and inside the coloured band, so the box has
        # an edge whatever it is drawn over.
        draw.rectangle([x1 - 1, y1 - 1, x2 + 1, y2 + 1],
                       outline=(20, 20, 24), width=line + 2)
        draw.rectangle([x1, y1, x2, y2], outline=colour, width=line)

    # Labels are placed one at a time, each nudged clear of the ones already
    # down. Objects that sit together - a bench, the backpack on it, the bicycle
    # leaning against it - have box tops at similar heights, so without this
    # their labels land on the same line and cover each other's text.
    # Topmost box first, so the cascade runs downwards and stays predictable.
    placed = []
    for d in sorted(detections, key=lambda d: (d["box"][1], d["box"][0])):
        x1, y1, _, y2 = d["box"]
        colour = PALETTE[labels.index(d["object"]) % len(PALETTE)]

        tag = f'{d["object"]} {d["confidence"]:.0%}'
        l, t, r, b = _text_box(draw, tag, font)
        bw, bh = (r - l) + pad * 2, (b - t) + pad * 2

        # Pulled left when the label would run off the right edge of the image.
        tx = max(0, min(x1, img.width - bw))

        # Above the box first, then just inside its top, then stepping down its
        # leading edge. The first position that is on the image and clear of
        # every label already drawn wins.
        spot = None
        for ty in (y1 - bh, y1, y1 + bh, y1 + bh * 2, y2 - bh):
            if ty < 0 or ty + bh > img.height:
                continue
            cand = (tx, ty, tx + bw, ty + bh)
            if not any(_hits(cand, q) for q in placed):
                spot = cand
                break

        if spot is None:
            # Everything collided. Better an overlapping label than a missing
            # one, so fall back to the preferred spot, clamped onto the image.
            ty = max(0, min(y1 - bh if y1 - bh >= 0 else y1, img.height - bh))
            spot = (tx, ty, tx + bw, ty + bh)

        placed.append(spot)
        draw.rectangle(list(spot), fill=colour)
        draw.text((spot[0] + pad - l, spot[1] + pad - t), tag,
                  fill=_text_on(colour), font=font)

    img.save(out_path)
    return out_path


def default_out_path(image_path):
    stem, ext = os.path.splitext(image_path)
    return f"{stem}_detected{ext or '.jpg'}"


# --------------------------------------------------------------------------
# Backends. Imported only when used, so --list works with nothing installed.
# --------------------------------------------------------------------------
def _ultralytics(cfg, path, conf):
    from ultralytics import YOLO
    model = YOLO(cfg["weights"])
    out = []
    for box in model(path, verbose=False)[0].boxes:
        c = float(box.conf[0])
        if c < conf:
            continue
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        out.append({"object": model.names[int(box.cls[0])], "confidence": round(c, 3),
                    "box": [round(x1), round(y1), round(x2), round(y2)]})
    return out


def _torchvision(cfg, path, conf):
    import torch
    from torchvision.transforms.functional import pil_to_tensor
    from torchvision.models.detection import (
        fasterrcnn_resnet50_fpn_v2, FasterRCNN_ResNet50_FPN_V2_Weights,
        maskrcnn_resnet50_fpn_v2, MaskRCNN_ResNet50_FPN_V2_Weights)
    from PIL import Image
    if cfg["name"].startswith("Faster"):
        w, ctor = FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT, fasterrcnn_resnet50_fpn_v2
    else:
        w, ctor = MaskRCNN_ResNet50_FPN_V2_Weights.DEFAULT, maskrcnn_resnet50_fpn_v2
    model = ctor(weights=w).eval()
    names = w.meta["categories"]
    # Loaded through PIL like every other backend rather than torchvision's
    # read_image, which handles only JPEG and PNG and hands back whatever
    # channel count the file has - 4 for a PNG with transparency, 1 for
    # greyscale - neither of which these models accept. convert("RGB") settles
    # the channels and opens up every format PIL reads.
    img = Image.open(path).convert("RGB")
    with torch.no_grad():
        pred = model([w.transforms()(pil_to_tensor(img))])[0]
    out = []
    for box, label, score in zip(pred["boxes"], pred["labels"], pred["scores"]):
        s = float(score)
        if s < conf:
            continue
        x1, y1, x2, y2 = [round(float(v)) for v in box.tolist()]
        out.append({"object": names[int(label)], "confidence": round(s, 3),
                    "box": [x1, y1, x2, y2]})
    return out


def _rfdetr(cfg, path, conf):
    import rfdetr
    from PIL import Image
    # Only the Apache-2.0 sizes are ever built here; XL/2XL are PML-1.0.
    det = rfdetr.RFDETRBase().predict(Image.open(path).convert("RGB"), threshold=conf)
    try:
        from rfdetr.util.coco_classes import COCO_CLASSES as names
    except Exception:  # noqa: BLE001
        names = None
    out = []
    for box, cid, score in zip(det.xyxy, det.class_id, det.confidence):
        x1, y1, x2, y2 = [round(float(v)) for v in box]
        label = names[int(cid)] if names and int(cid) < len(names) else str(int(cid))
        out.append({"object": label, "confidence": round(float(score), 3),
                    "box": [x1, y1, x2, y2]})
    return out


def _rtdetr(cfg, path, conf):
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModelForObjectDetection
    ckpt = os.environ.get("RTDETR_CHECKPOINT", "PekingU/rtdetr_r50vd")
    # RT-DETR is Apache-2.0 from Baidu's release; the ultralytics build of the
    # same architecture is AGPL-3.0, so that source is refused here.
    if "ultralytics" in ckpt.lower():
        raise ValueError("RT-DETR from an ultralytics source is AGPL-3.0, not "
                         "Apache-2.0. Use a 'PekingU/rtdetr_*' checkpoint.")
    proc = AutoImageProcessor.from_pretrained(ckpt)
    model = AutoModelForObjectDetection.from_pretrained(ckpt).eval()
    img = Image.open(path).convert("RGB")
    with torch.no_grad():
        outputs = model(**proc(images=img, return_tensors="pt"))
    res = proc.post_process_object_detection(
        outputs, target_sizes=torch.tensor([img.size[::-1]]), threshold=conf)[0]
    out = []
    for score, label, box in zip(res["scores"], res["labels"], res["boxes"]):
        x1, y1, x2, y2 = [round(float(v)) for v in box.tolist()]
        out.append({"object": model.config.id2label[int(label)],
                    "confidence": round(float(score), 3), "box": [x1, y1, x2, y2]})
    return out


BACKENDS = {"ultralytics": _ultralytics, "torchvision": _torchvision,
            "rfdetr": _rfdetr, "rtdetr": _rtdetr}


# --------------------------------------------------------------------------
def show_list():
    """Grouped by pip package on purpose. The usual question is "do I need a
    separate install for every model?" - no: 4 packages cover all 9, and one
    is enough to start."""
    print()
    print(f"find_objects {__version__} - 9 models across 4 packages. You need ONE.")
    print()

    groups = {}
    for key in AUTO_ORDER:
        groups.setdefault(MODELS[key]["pip"], []).append(key)
    # packages giving business-safe models first, then bigger bundles first
    order = sorted(groups, key=lambda pip: (
        not MODELS[groups[pip][0]]["free_for_business"], -len(groups[pip])))

    for pip in order:
        keys = groups[pip]
        have = backend_available(MODELS[keys[0]]["backend"])
        tag = "  [installed]" if have else ""
        warn = "" if MODELS[keys[0]]["free_for_business"] else "   <- not free for business use"
        plural = "models" if len(keys) > 1 else "model "
        print(f"  {pip:<30} {len(keys)} {plural}{tag}{warn}")
        for k in keys:
            m = MODELS[k]
            print(f"      --model {k:<12}{m['name']:<18}{m['ms']:>7.1f}ms   "
                  f"COCO {m['map']:<6}{m['licence']}")
        print()

    auto = pick_auto()
    if auto:
        print(f"  Right now it uses: {MODELS[auto]['name']} (already installed)")
    else:
        print(f"  Nothing installed yet. Start with:  {MODELS['rfdetr']['pip']}")
    print("  Speeds are medians over 48 scenes on one V100 - they compare the")
    print("  models to each other, not to your hardware. COCO is each vendor's")
    print(f"  own published accuracy figure. Full comparison: {SITE}")
    print()


def fail(msg, **extra):
    print(json.dumps({"ok": False, "error": msg, **extra}, indent=2))
    return 1


def main():
    p = argparse.ArgumentParser(
        description="Find objects in an image and draw boxes on a copy of it.",
        epilog=f"Compare all 9 models on identical scenes: {SITE}")
    p.add_argument("image", nargs="?", help="image file to look at")
    p.add_argument("--model", default="auto", help="model to use (default: auto). See --list")
    p.add_argument("--conf", type=float, default=0.25, help="min confidence, 0-1 (default 0.25)")
    p.add_argument("--out", help="where to save the annotated image")
    p.add_argument("--no-image", action="store_true", help="don't save an annotated image")
    p.add_argument("--commercial", action="store_true",
                   help="only use models that are free for business use")
    p.add_argument("--list", action="store_true", help="list the models and exit")
    p.add_argument("--version", action="version", version=f"find_objects {__version__}")
    args = p.parse_args()

    if args.list:
        show_list()
        return 0
    if not args.image:
        p.print_usage()
        return fail("Give me an image, e.g. find_objects.py photo.jpg")
    if not os.path.isfile(args.image):
        return fail(f"No such file: {args.image}")

    # ---- choose a model -------------------------------------------------
    key = args.model.lower()
    if key == "auto":
        key = pick_auto()
        if key is None:
            return fail("No detection model installed yet.",
                        fix=MODELS["rfdetr"]["pip"],
                        note="That one is free for commercial use. Others: --list")
    if key not in MODELS:
        return fail(f"Unknown model '{args.model}'.", choices=sorted(MODELS))

    cfg = MODELS[key]
    if args.commercial and not cfg["free_for_business"]:
        alt = next(k for k in AUTO_ORDER if MODELS[k]["free_for_business"])
        return fail(
            f"{cfg['name']} is {cfg['licence']}, which is not free for commercial use. "
            f"You passed --commercial, so it was not used.",
            try_instead=f"--model {alt}  ({MODELS[alt]['name']}, {MODELS[alt]['licence']})")

    if not backend_available(cfg["backend"]):
        return fail(f"{cfg['name']} needs a package that isn't installed.",
                    fix=cfg["pip"], model=cfg["name"])

    # ---- run ------------------------------------------------------------
    try:
        detections = BACKENDS[cfg["backend"]](cfg, args.image, args.conf)
    except ImportError as e:
        # The pre-flight check above only proves the package exists on disk,
        # not that it imports. The usual real-world failure is version skew:
        # "cannot import name 'X' from 'Y'" means Y is too OLD for something
        # else in the chain - not that anything is missing. Say which package
        # to upgrade instead of passing the raw traceback along.
        stale = re.search(r"from '([\w.]+)'", str(e))
        if stale:
            pkg = stale.group(1).split(".")[0]
            return fail(
                f"{cfg['name']} could not start because '{pkg}' is out of date.",
                detail=str(e),
                fix=f"pip install --upgrade {pkg}",
                why=(f"'{pkg}' is installed but older than {cfg['name']}'s other "
                     f"dependencies expect. pip left it alone because something "
                     f"already required it."),
                model=cfg["name"])
        return fail(f"{cfg['name']} is missing a dependency.",
                    detail=str(e), fix=cfg["pip"], model=cfg["name"])
    except Exception as e:  # noqa: BLE001
        return fail(f"{type(e).__name__}: {e}", model=cfg["name"])

    counts = {}
    for d in detections:
        counts[d["object"]] = counts.get(d["object"], 0) + 1
    summary = ", ".join(f"{n} {o}" + ("s" if n > 1 and not o.endswith("s") else "")
                        for o, n in sorted(counts.items(), key=lambda kv: -kv[1])) or "nothing"

    result = {
        "ok": True,
        "found": summary,
        "count": len(detections),
        "objects": counts,
        "detections": detections,
        "image": args.image,
        "model": cfg["name"],
        "model_licence": cfg["licence"],
        "free_for_business_use": cfg["free_for_business"],
    }

    if not args.no_image:
        out_path = args.out or default_out_path(args.image)
        try:
            result["annotated_image"] = draw_boxes(args.image, detections, out_path)
        except Exception as e:  # noqa: BLE001 - detection worked; say so and move on
            result["annotated_image"] = None
            result["image_error"] = f"Could not draw boxes: {type(e).__name__}: {e}"

    if not cfg["free_for_business"]:
        result["note"] = (
            f"{cfg['name']} is {cfg['licence']} - fine for personal, research and "
            f"open-source work, but not free to use in a commercial product. "
            f"Run with --commercial to use a model that is.")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
