"""
=============================================================================
GPUMDkit: A User-Friendly Toolkit for GPUMD and NEP
Repository: https://github.com/zhyan0603/GPUMDkit
Citation: Z. Yan et al., GPUMDkit: A User-Friendly Toolkit for GPUMD and NEP,
          MGE Advances, 2026, e70074 (https://doi.org/10.1002/mgea.70074)
=============================================================================
Script:     pos2model_xyz.py
Category:   Format Conversion Scripts
Purpose:    Convert a POSCAR / *.vasp / *.xyz structure file in the current
            directory into a single model.xyz (extxyz format). The original
            file is kept unchanged. For xyz files, a specific frame can be
            extracted by a 0-based frame index (same as OVITO).
Usage:      python pos2model_xyz.py [filename] [frame_index]
Arguments:
  filename     Optional: target structure file. When omitted, the script
               auto-detects the only candidate file (POSCAR / *.vasp /
               *.xyz) in the current directory; if multiple candidates
               exist, you must specify one explicitly.
  frame_index  Optional: 0-based frame index, only valid for xyz files
               (0 = the first frame). Default: 0.
Examples:
  python pos2model_xyz.py             # convert the only candidate file
  python pos2model_xyz.py xxx.vasp    # convert a specified VASP file
  python pos2model_xyz.py B.xyz       # convert the 1st frame of B.xyz
  python pos2model_xyz.py B.xyz 5     # convert the 6th frame of B.xyz
  python pos2model_xyz.py 2           # convert the 3rd frame of the only xyz
Output:
  model.xyz  (converted structure in extxyz format)
Author:     Zihan YAN (yanzihan@westlake.edu.cn)
Last-modified: 2026-08-21
=============================================================================
"""

import glob
import os
import sys

from ase.io import read, write

OUTPUT_FILE = "model.xyz"


def find_candidates():
    """Find candidate structure files (POSCAR / *.vasp / *.xyz) in the
    current directory, excluding the output file itself."""
    candidates = []
    for pattern in ["POSCAR", "*.vasp", "*.xyz"]:
        candidates.extend(glob.glob(pattern))
        candidates.extend(glob.glob(pattern.upper()))
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    # Exclude the output file itself (e.g. model.xyz generated last time)
    return [c for c in unique if c != OUTPUT_FILE]


def is_vasp_file(filename):
    return filename == "POSCAR" or filename.lower().endswith(".vasp")


def is_xyz_file(filename):
    return filename.lower().endswith(".xyz")


def main():
    args = sys.argv[1:]
    filename = None
    frame_index = 0

    if not args:
        # Auto-detect the only candidate file in the current directory
        candidates = find_candidates()
        if not candidates:
            print("No structure file (POSCAR / *.vasp / *.xyz) found in the current directory.")
            sys.exit(1)
        if len(candidates) > 1:
            print("Multiple structure files found in the current directory:")
            for c in candidates:
                print(f"  {c}")
            print("Please specify one explicitly, e.g.:")
            print(f"  python {os.path.basename(__file__)} <filename> [frame_index]")
            sys.exit(1)
        filename = candidates[0]
    elif args[0].isdigit():
        # Frame-index mode: only valid when there is exactly one xyz file
        if len(args) > 1:
            print("Usage: python pos2model_xyz.py [filename] [frame_index]")
            sys.exit(1)
        frame_index = int(args[0])
        xyz_candidates = [c for c in find_candidates() if is_xyz_file(c)]
        if not xyz_candidates:
            print("No xyz file found in the current directory.")
            sys.exit(1)
        if len(xyz_candidates) > 1:
            print("Multiple xyz files found in the current directory:")
            for c in xyz_candidates:
                print(f"  {c}")
            print("Please specify the file explicitly, e.g.:")
            print(f"  python {os.path.basename(__file__)} <filename.xyz> {args[0]}")
            sys.exit(1)
        filename = xyz_candidates[0]
    else:
        filename = args[0]
        if len(args) > 2:
            print("Usage: python pos2model_xyz.py [filename] [frame_index]")
            sys.exit(1)
        if len(args) == 2:
            if not args[1].isdigit():
                print("Error: the second argument must be an integer frame index.")
                sys.exit(1)
            frame_index = int(args[1])

    if not os.path.exists(filename):
        print(f"Error: file '{filename}' does not exist.")
        sys.exit(1)

    # Read the structure
    if is_vasp_file(filename):
        if frame_index != 0:
            print(f"Warning: {filename} is a single-frame VASP file, the frame index is ignored.")
        atoms = read(filename, format="vasp")
        frame_desc = "frame 0"
    elif is_xyz_file(filename):
        frames = read(filename, index=":")
        if frame_index < 0 or frame_index >= len(frames):
            print(f"Error: frame {frame_index} is out of range. The file contains {len(frames)} frames.")
            sys.exit(1)
        atoms = frames[frame_index]
        frame_desc = f"frame {frame_index}"
    else:
        print(f"Error: unsupported file type: {filename}")
        sys.exit(1)

    # Write to model.xyz in extxyz format so that the lattice is preserved
    if os.path.exists(OUTPUT_FILE):
        print(f"Note: {OUTPUT_FILE} already exists, it will be overwritten.")
    write(OUTPUT_FILE, atoms, format="extxyz")
    print(f"Done! Converted {filename} ({frame_desc}) to {OUTPUT_FILE}.")


if __name__ == "__main__":
    main()
