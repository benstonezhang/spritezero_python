#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import math
import os
import sys

import cairocffi as cairo
from cairosvg import parser, surface
from rectpack import newPacker


def usage():
    print(f'''Generate sprite sheets for maps and the web using SVG files as input
    usage: {sys.argv[0]} output_prefix icons_dir [--retina]''')
    exit(1)


scale = 1
for i in range(1, len(sys.argv)):
    if sys.argv[i] == '--retina':
        scale = 2
        sys.argv.pop(i)
        break

if len(sys.argv) < 3:
    usage()

output_prefix = sys.argv[1]
icons_dir = sys.argv[2]

icon_bytes = {}
icons = []

area = 0
min_unit_width = sys.maxsize
max_unit_width = 0
min_unit_height = sys.maxsize
max_unit_height = 0


def parse_as_int(s: str):
    try:
        return int(s)
    except ValueError:
        return int(float(s))


count = 0
for fname in os.listdir(icons_dir):
    if fname[-4:] != '.svg':
        continue

    svg_path = os.path.join(icons_dir, fname)
    with open(svg_path, 'r') as fp:
        buf = fp.read()
    svg = parser.Tree(bytestring=buf, url=svg_path)

    icon_name = fname[:-4]
    width = parse_as_int(svg['width'])
    height = parse_as_int(svg['height'])

    icon = icon_bytes.get(buf)
    if icon is not None:
        icon['name'].append(icon_name)
        continue

    icon = {'name': [icon_name, ], 'width': width, 'height': height, 'obj': svg}
    icon_bytes[buf] = icon
    icons.append(icon)

    area += width * height
    if width < min_unit_width:
        min_unit_width = width
    if width > max_unit_width:
        max_unit_width = width
    if height < min_unit_height:
        min_unit_height = height
    if height > max_unit_height:
        max_unit_height = height
    count += 1

del icon_bytes
print(f'Total {count} icons ({count - len(icons)} duplicated), sum of area is {area}, \
unit width: {min_unit_width}-{max_unit_width}, unit height: {min_unit_height}-{max_unit_height}')

min_area = sys.maxsize
best_pack = 0

for width in range(max_unit_width, max_unit_width * (int(math.sqrt(area) * 2) // max_unit_width), max_unit_width):
    packer = newPacker(rotation=False)
    packer.add_bin(width, 10 * area // width)
    for i, icon in enumerate(icons):
        packer.add_rect(icon['width'], icon['height'], i)
    packer.pack()
    min_height = 0
    for rect in packer[0]:
        if rect.top > min_height:
            min_height = rect.top
    sub_area = width * min_height
    print(f'{width}x{min_height}: {sub_area}')
    if sub_area < min_area:
        min_area = sub_area
        best_pack = packer[0]
        best_pack.height = min_height

print(f'Best Fit in {best_pack.width}x{best_pack.height}:')

sprite = {}
sprite_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, best_pack.width * scale, best_pack.height * scale)
sprite_context = cairo.Context(sprite_surface)

for rect in best_pack:
    icon = icons[rect.rid]
    icon['width'] = rect.width * scale
    icon['height'] = rect.height * scale
    icon['left'] = rect.left * scale
    icon['top'] = (best_pack.height - rect.top) * scale
    names = icon['name']
    print(f'  {names}: ({rect.left},{rect.top}) {rect.width}x{rect.height}')

    for icon_name in names:
        sprite[icon_name] = {
            "width": icon['width'],
            "height": icon['height'],
            "pixelRatio": scale,
            "x": icon['left'],
            "y": icon['top'],
        }

    draw = surface.PNGSurface(icon['obj'], output=None, dpi=72, scale=scale)
    sprite_context.set_source_surface(draw.cairo, icon['left'], icon['top'])
    sprite_context.rectangle(icon['left'], icon['top'], icon['width'], icon['height'])
    sprite_context.fill()
    draw.cairo.finish()
    del draw

with open(output_prefix + '.json', 'w') as fp:
    json.dump(sprite, fp, indent=2, sort_keys=True)

sprite_surface.write_to_png(output_prefix + '.png')
sprite_surface.finish()
