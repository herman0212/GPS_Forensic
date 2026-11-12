
from datasets import load_dataset
from pathlib import Path
import csv
import re

DATASET_NAME = "Oelnesr1/Image2GPS-25"
OUTPUT_DIR = Path("data/Image2GPS25")
IMAGES_DIR = OUTPUT_DIR / "images"

IMAGES_DIR.mkdir(parents=True, exist_ok=True)

print("Dang ket noi")

dataset = load_dataset(
    DATASET_NAME,
    split="train",
    streaming=True
)

LIMIT = 100
metadata = []

for i, row in enumerate(dataset):
    if i >= LIMIT:
        break

    image = row["image"]

    img_id = str(row.get("img_id") or i)
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", img_id)
    filename = f"{i:04d}_{safe_id}.jpg"

    image_path = IMAGES_DIR / filename
    image.convert("RGB").save(
        image_path,
        format="JPEG",
        quality=95
    )

    metadata.append({
        "filename": filename,
        "img_id": img_id,
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "gps_altitude": row.get("gps_altitude"),
        "timestamp": row.get("timestamp"),
        "timestamp_raw": row.get("timestamp_raw"),
        "camera_make": row.get("camera_make"),
        "camera_model": row.get("camera_model"),
        "split": row.get("split")
    })

    print(f"[{i + 1}/{LIMIT}] Da tai {filename}")

if metadata:
    csv_path = OUTPUT_DIR / "metadata.csv"

    with open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=metadata[0].keys()
        )
        writer.writeheader()
        writer.writerows(metadata)

    print("\nTAI DU LIEU THANH CONG!")
    print("So anh:", len(metadata))
    print("Thu muc:", IMAGES_DIR.resolve())
    print("Metadata:", csv_path.resolve())
else:
    print("Khong co du lieu duoc tai.")
