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
usage: {sys.argv[0]} output_prefix icons_dir [--retina] [--reuse-json] [--verbose]''')
    exit(1)


verbose = False
scale = 1
reuse_json = False

i = 0
while i < len(sys.argv):
    if sys.argv[i] == '--verbose':
        verbose = True
        sys.argv.pop(i)
    elif sys.argv[i] == '--retina':
        scale = 2
        sys.argv.pop(i)
    elif sys.argv[i] == '--reuse-json':
        reuse_json = True
        sys.argv.pop(i)
    else:
        i += 1

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
if verbose:
    print(f'Total {count} icons ({count - len(icons)} duplicated), sum of area is {area}, \
unit width: {min_unit_width}-{max_unit_width}, unit height: {min_unit_height}-{max_unit_height}')


def check_json_match(sprite):
    icons_map = {name: icon for icon in icons for name in icon['name']}
    for name, icon_pos in sprite.items():
        icon = icons_map.get(name)
        if icon_pos['pixelRatio'] != scale or icon is None or icon_pos['width'] != icon['width'] or \
                icon_pos['height'] != icon['height']:
            return False
    return True


if reuse_json:
    with open(output_prefix + '.json', 'r') as fp:
        sprite = json.load(fp)

    if check_json_match(sprite) is False:
        print('icons not match')
        exit(1)

if reuse_json:
    best_width = 0
    best_height = 0
    for icon in sprite.values():
        if icon['x'] + icon['width'] > best_width:
            best_width = icon['x'] + icon['width']
        if icon['y'] + icon['height'] > best_height:
            best_height = icon['y'] + icon['height']
    if verbose:
        print(f'Best Fit in {best_width // scale}x{best_height // scale}:')
else:
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
        if verbose:
            print(f'{width}x{min_height}: {sub_area}')
        if sub_area < min_area:
            min_area = sub_area
            best_pack = packer[0]
            best_pack.height = min_height

    if verbose:
        print(f'Best Fit in {best_pack.width}x{best_pack.height}:')

    best_width = best_pack.width * scale
    best_height = best_pack.height * scale

sprite_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, best_width, best_height)
sprite_context = cairo.Context(sprite_surface)

if reuse_json:
    for icon in icons:
        icon_pos = sprite.get(icon['name'][0])
        if icon_pos is None:
            continue
        draw = surface.PNGSurface(icon['obj'], output=None, dpi=72, scale=scale)
        sprite_context.set_source_surface(draw.cairo, icon_pos['x'], icon_pos['y'])
        sprite_context.rectangle(icon_pos['x'], icon_pos['y'], icon_pos['width'], icon_pos['height'])
        sprite_context.fill()
        draw.cairo.finish()
        del draw
else:
    sprite = {}

    for rect in best_pack:
        icon = icons[rect.rid]
        icon['width'] = rect.width * scale
        icon['height'] = rect.height * scale
        icon['left'] = rect.left * scale
        icon['top'] = (best_pack.height - rect.top) * scale
        names = icon['name']
        if verbose:
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
