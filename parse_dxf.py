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
    parser.add_argument('--split', type=str, default="dxf",
                        help='the split of dataset')
    parser.add_argument('--data_dir', type=str, default="./jem_dataset",
                        help='save the downloaded data')
    args = parser.parse_args()
    return args

def get_thickness(entity):
    thickness = entity.dxf.lineweight
    if thickness== -1:
        
        if hasattr(entity, 'layer') and entity.layer.dxf.lineweight != -1:
            thickness = entity.layer.dxf.lineweight
        else:
            if hasattr(entity, 'block') and entity.block.dxf.lineweight != -1:
                thickness = entity.block.dxf.lineweight
            else:
                thickness = 0
    return thickness

def get_color(doc, entity):
    aci_color = entity.dxf.color
    if aci_color == 256:
        layer = doc.layers.get(entity.dxf.layer)
        aci_color = layer.get_color()
    rgb = ezdxf.colors.aci2rgb(aci_color)
    return rgb

def process_line(doc, entity, start, end):        
    length = math.dist(start, end)
    rgb = get_color(doc, entity)
    
    thickness = get_thickness(entity)

    inds = [0, 1/3, 2/3, 1.0]
    lx, ly = end[0] - start[0], end[1] - start[1]

    arg = [[start[0] + lx * ind, start[1] + ly * ind] for ind in inds]
    
    return length, rgb, thickness, arg
    
def process_circle(doc, entity):
    center = entity.dxf.center
    cx, cy = float(center.x), float(center.y)
    r = entity.dxf.radius

    length = 2 * math.pi * r
    rgb = get_color(doc, entity)
    thickness = get_thickness(entity)
    
    thetas = [0,math.pi/2, math.pi, 3 * math.pi/2]
    arg = [[cx + r * math.cos(theta), cy + r * math.sin(theta)] for theta in thetas]

    return length, rgb, thickness, arg


def process_ellipse(doc, entity):
    center = entity.dxf.center
    cx, cy = float(center.x), float(center.y)
    major_axis = entity.dxf.major_axis
    
    a = math.dist(major_axis, [0, 0, 0])
    r = entity.dxf.ratio

    b = a * r

    length = 2 * math.pi *b + 4*(a - b)
    rgb = get_color(doc, entity)
    thickness = get_thickness(entity)

    thetas = [0, math.pi/2, math.pi, 3 * math.pi/2]
    arg = [[cx + a * math.cos(theta), cy + b * math.sin(theta)] for theta in thetas]

    return length, rgb, thickness, arg


def process_arc(doc, entity):
    center = entity.dxf.center
    cx, cy = float(center.x), float(center.y)
    r = entity.dxf.radius
    
    start_theta, end_theta = entity.dxf.start_angle, entity.dxf.end_angle
    d_theta = abs(end_theta - start_theta)
    
    length =  2 * math.pi * r * d_theta / 360 
    rgb = get_color(doc, entity)
    thickness = get_thickness(entity)
    
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
            length, rgb, thickness, arg = process_line(doc, entity, start, end)
            
            commands.append(COMMANDS.index("line"))
            layerIds.append(layerId)
            lengths.append(length)
            strokes.append(rgb)
            widths.append(thickness)
            args.append(arg)

        for entity in msp.query(f"LWPOLYLINE{query}"):
            points = entity.get_points()
            
            if entity.closed: segments = list(zip(points, points[1:] + points[:1]))
            else: segments = list(zip(points, points[1:]))
            
            for start, end in segments:
                length, rgb, thickness, arg = process_line(doc, entity, start, end)
                
                commands.append(COMMANDS.index("line"))
                layerIds.append(layerId)
                lengths.append(length)
                strokes.append(rgb)
                widths.append(thickness)
                args.append(arg)

        for entity in msp.query(f"POLYLINE{query}"):
            points = list(entity.points())
            
            print(f"p {points}")

            if entity.is_closed: 
                segments = list(zip(points, points[1:] + points[:1]))
            else: 
                segments = list(zip(points, points[1:]))
            
            for start, end in segments:
                length, rgb, thickness, arg = process_line(doc, entity, start, end)
                
                commands.append(COMMANDS.index("line"))
                layerIds.append(layerId)
                lengths.append(length)
                strokes.append(rgb)
                widths.append(thickness)
                args.append(arg)

        for entity in msp.query(f"CIRCLE{query}"):
            length, rgb, thickness, arg = process_circle(doc, entity)

            commands.append(COMMANDS.index("circle"))
            layerIds.append(layerId)
            lengths.append(length)
            strokes.append(rgb)
            widths.append(thickness)
            args.append(arg)

        for entity in msp.query(f"ELLIPSE{query}"):
            length, rgb, thickness, arg = process_ellipse(doc, entity)
            
            commands.append(COMMANDS.index("circle"))
            layerIds.append(layerId)
            lengths.append(length)
            strokes.append(rgb)
            widths.append(thickness)
            args.append(arg)

        for entity in msp.query(f"ARC{query}"):
            length, rgb, thickness, arg = process_arc(doc, entity)

            commands.append(COMMANDS.index("circle"))
            layerIds.append(layerId)
            lengths.append(length)
            strokes.append(rgb)
            widths.append(thickness)
            args.append(arg)


    non_zero_widths = [th for th in widths if th > 0]
    
    if non_zero_widths: avg_thickness = int(sum(non_zero_widths) / len(non_zero_widths))
    else: avg_thickness = 50

    widths = [avg_thickness if th == 0 else th for th in widths]

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
    dxf_paths = glob.glob(os.path.join(args.data_dir, args.split,'*.dxf'))
    
    save_dir = os.path.join(args.data_dir,"jsons")
    os.makedirs(save_dir,exist_ok=True)
    
    inputs = []
    for dxf_path in dxf_paths: inputs.append([dxf_path, save_dir])

    mmcv.track_parallel_progress(process,inputs,64)
