import math,re
import os,glob,json
import ezdxf
from ezdxf import bbox
from collections import defaultdict
import numpy as np
import mmcv, argparse

LABEL_NUM = 35
COMMANDS = ['line', 'arc','circle', 'ellipse']

def parse_args():
    '''
    Arguments
    '''
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--split', type=str, default="test",
                        help='the split of dataset')
    parser.add_argument('--data_dir', type=str, default="./dataset/jem",
                        help='save the downloaded data')
    args = parser.parse_args()
    return args

def process_line(entity, start, end):        
    length = math.dist(start, end)
    rgb = entity.dxf.color.get_rgb()
    thickness = entity.dxf.thickness

    inds = [0, 1/3, 2/3, 1.0]
    lx, ly = end[0] - start[0], end[1] - start[1]

    arg = [[start[0] + lx * ind, start[1] + ly * ind] for ind in inds]
    
    return length, rgb, thickness, arg
    
def process_circle(entity):
    cx, cy = entity.dxf.center
    r = entity.dxf.radius

    length = 2 * math.pi * r
    rgb = entity.dxf.color.get_rgb()
    thickness = entity.dxf.thickness
    
    thetas = [0,math.pi/2, math.pi, 3 * math.pi/2]
    arg = [[cx + r * math.cos(theta), cy + r * math.sin(theta)] for theta in thetas]

    return length, rgb, thickness, arg


def process_ellipse(entity):
    cx, cy = entity.dxf.center
    a = entity.dxf.major_axis
    r = entity.dxf.ratio

    b = a * r

    length = 2 * math.pi *b + 4*(a - b)
    rgb = entity.dxf.color.get_rgb()
    thickness = entity.dxf.thickness

    thetas = [0,math.pi/2, math.pi, 3 * math.pi/2]
    arg = [[cx + a * math.cos(theta), cy + b * math.sin(theta)] for theta in thetas]

    return length, rgb, thickness, arg


def process_arc(entity):
    cx, cy = entity.dxf.center
    r = entity.dxf.radius
    
    start_theta, end_theta = entity.dxf.start_angle, entity.dxf.end_angle
    d_theta = math.abs(end_theta - start_theta)
    
    length =  2 * math.pi * r * d_theta / 360 
    rgb = entity.dxf.color.get_rgb()
    thickness = entity.dxf.thickness
    
    parts = [0, 1/3, 2/3, 1]
    thetas = [start_theta + d_theta * part for part in parts]

    arg = [[cx + r * math.cos(theta), cy + r * math.sin(theta)] for theta in thetas]
    
    return length, rgb, thickness, arg

def parse_dxf(dxf_file):
    doc = ezdxf.readfile(dxf_file)
    msp = doc.modelspace()
    
    extents = bbox.extents(msp)
    min_x, min_y, _ = extents.extmin
    max_x, max_y, _ = extents.extmax

    width = max_x - min_x
    height = max_y - min_y

    commands = []
    args = [] # (x1,y1,x2,y2,x3,y3,x4,y4) 4points
    lengths = []
    strokes = []
    layerIds = []
    widths = []

    for layerId, layer in enumerate(doc.layers):
        query  =  f"[layer == '{layer.dxf.name}']"
        
        for entity in msp.query(f"LINE{query}"):
            start, end = entity.dxf.start, entity.dxf.end
            length, rgb, thickness, arg = process_line(entity, start, end)
            
            commands.append(COMMANDS.index("line"))
            layerIds.append(layerId)
            lengths.append(length)
            strokes.append(rgb)
            widths.append(thickness)
            args.append(arg)

        for entity in msp.query(f"LWPOLYLINE{query}", f"POLYLINE{query}"):
            points = entity.get_points()
            
            if entity.closed: segments = list(zip(points, points[1:] + points[:1]))
            else: segments = list(zip(points, points[1:]))
            
            for start, end in segments:
                length, rgb, thickness, arg = process_line(entity, start, end)
                
                commands.append(COMMANDS.index("line"))
                layerIds.append(layerId)
                lengths.append(length)
                strokes.append(rgb)
                widths.append(thickness)
                args.append(arg)



        for entity in msp.query(f"CIRCLE{query}"):
            length, rgb, thickness, arg = process_circle(entity)

            commands.append(COMMANDS.index("circle"))
            layerIds.append(layerId)
            lengths.append(length)
            strokes.append(rgb)
            widths.append(thickness)
            args.append(arg)

        for entity in msp.query(f"ELLIPSE{query}"):
            length, rgb, thickness, arg = process_ellipse(entity)
            
            commands.append(COMMANDS.index("circle"))
            layerIds.append(layerId)
            lengths.append(length)
            strokes.append(rgb)
            widths.append(thickness)
            args.append(arg)

        for entity in msp.query(f"ARC{query}"):
            length, rgb, thickness, arg = process_arc(entity)

            commands.append(COMMANDS.index("circle"))
            layerIds.append(layerId)
            lengths.append(length)
            strokes.append(rgb)
            widths.append(thickness)
            args.append(arg)

    json_dicts = {
        "commands":commands,
        "args":args,
        "lengths":lengths,
        "width":width,
        "height":height,
        "rgb": strokes,
        "layerIds":layerIds,
        "widths": widths
    }
    return json_dicts

def save_json(json_dicts,out_json):
    json.dump(json_dicts, open(out_json, 'w'), indent=4)
    

def process(data):
    
    dxf_file, save_dir = data
    json_dicts = parse_dxf(dxf_file)
    filename = dxf_file.split("/")[-1].replace(".dxf",".json")
    
    out_json = os.path.join(save_dir,filename)
    save_json(json_dicts,out_json)

if __name__=="__main__":
    
    args = parse_args()
    svg_paths = glob.glob(os.path.join(args.data_dir,'*.dxf'))
    
    save_dir = os.path.join("./dataset/",args.split, "jsons")
    os.makedirs(save_dir,exist_ok=True)
    
    inputs = []
    for dxf_path in svg_paths: inputs.append([dxf_path, save_dir])

    mmcv.track_parallel_progress(process,inputs,64)