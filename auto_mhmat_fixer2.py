"""
MakeHuman 2 Auto MHMAT converter (PBR material converter from deprecrated Phong)
Contributed to the MH2 Community by Elvaerwyn_MH2 2026 with suggestions added from Punkduck
"""

import os
import glob


def convert_mhmat_to_pbr(filepath):
    """
    Converts a legacy .mhmat file to MakeHuman 2 PBR shader format.
    Returns (converted_bool, summary_line).
    """
    accepted_keys = [
        "diffuseTexture", "normalmapTexture", "aomapTexture", "metallicRoughnessTexture",
        "emissiveTexture", "maskTexture",
        "name", "description", "tag", "transparent", "alphaToCoverage", "backfaceCull",
        "ambientColor", "diffuseColor", "emissiveColor", "specularColor", "colorationColor",
        "glassColor", "colorationMethod",
        "normalmapIntensity", "roughnessFactor", "metallicFactor", "emissiveFactor",
        "transmission", "glassRoughness", "ior", "aomapIntensity"
    ]

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    # Skip if already converted to PBR
    if any(line.strip().lower() == "shader pbr" for line in lines):
        return False, f"Skipped (already PBR): {os.path.basename(filepath)}"

    ambient_change = not any("aomapTexture" in line for line in lines)
    final_lines = ["# Automatic converted mhmat file for PBR shader\n#\n"]
    maps = []

    for line in lines:
        stripped = line.strip()
        for key in accepted_keys:
            if stripped.startswith(key + " ") or stripped == key:
                if key == "ambientColor" and ambient_change:
                    final_lines.append("ambientColor 1.0 1.0 1.0\n")
                else:
                    final_lines.append(stripped + "\n")
                if key.endswith("Texture"):
                    maps.append(key)
                break

    final_lines.append("\nshader pbr\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(final_lines)

    mapline = " [" + " ".join(maps) + "]" if maps else " [no textures]"
    msg = f"Converted: {os.path.basename(filepath)}{mapline} (ambient fixed: {ambient_change})"
    print(msg)
    return True, msg


def convert_folder_mhmats_to_pbr(root_folder):
    """Recursively converts all .mhmat files under root_folder to PBR."""
    pattern = os.path.join(root_folder, "**", "*.mhmat")
    converted = 0
    skipped = 0
    logs = []
    for mhmat_file in glob.glob(pattern, recursive=True):
        ok, msg = convert_mhmat_to_pbr(mhmat_file)
        if ok:
            converted += 1
            logs.append(msg)
        else:
            skipped += 1
    return converted, skipped, logs


if __name__ == "__main__":
    c, s, _ = convert_folder_mhmats_to_pbr(".")
    print(f"Done. Converted: {c}, Skipped: {s}")
