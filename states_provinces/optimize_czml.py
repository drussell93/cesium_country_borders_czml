#!/usr/bin/env python3
"""
Optimize CZML files by simplifying polylines while maintaining visual quality.
Uses Douglas-Peucker algorithm for line simplification.
"""

import json
import math
from shapely.geometry import LineString
from shapely import simplify
import os

def cartographic_radians_to_coords(radians_list):
    """Convert flat list of cartographic radians to list of (lon, lat) tuples."""
    coords = []
    for i in range(0, len(radians_list), 3):
        lon_rad = radians_list[i]
        lat_rad = radians_list[i + 1]
        coords.append((lon_rad, lat_rad))
    return coords

def coords_to_cartographic_radians(coords):
    """Convert list of (lon, lat) tuples to flat list of cartographic radians."""
    radians = []
    for lon_rad, lat_rad in coords:
        radians.extend([lon_rad, lat_rad, 0])
    return radians

def simplify_polyline(coords, tolerance):
    """
    Simplify a polyline using Douglas-Peucker algorithm.
    
    Args:
        coords: List of (lon, lat) tuples in radians
        tolerance: Simplification tolerance in radians (smaller = more detail)
    
    Returns:
        Simplified list of (lon, lat) tuples
    """
    if len(coords) < 3:
        return coords
    
    # Create LineString and simplify
    line = LineString(coords)
    simplified = simplify(line, tolerance=tolerance, preserve_topology=True)
    
    return list(simplified.coords)

def optimize_czml(input_file, output_file, tolerance, target_name):
    """
    Optimize CZML file by simplifying polylines.
    
    Args:
        input_file: Input CZML file path
        output_file: Output CZML file path
        tolerance: Simplification tolerance in radians
        target_name: Name for the optimized dataset
    """
    print(f"\n{'='*60}")
    print(f"Optimizing: {input_file}")
    print(f"Output: {output_file}")
    print(f"Tolerance: {tolerance} radians ({math.degrees(tolerance):.4f} degrees)")
    print(f"{'='*60}")
    
    # Load CZML
    print("Loading CZML...")
    with open(input_file, 'r') as f:
        czml_data = json.load(f)
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"Original size: {original_size:.1f} MB")
    print(f"Original packets: {len(czml_data)}")
    
    # Update document name
    czml_data[0]['name'] = target_name
    
    # Process each polyline
    total_polylines = len(czml_data) - 1
    original_points = 0
    simplified_points = 0
    
    for i in range(1, len(czml_data)):
        packet = czml_data[i]
        
        if 'polyline' in packet and 'positions' in packet['polyline']:
            positions_data = packet['polyline']['positions']
            
            if 'cartographicRadians' in positions_data:
                radians = positions_data['cartographicRadians']
                original_points += len(radians) // 3
                
                # Convert to coordinates
                coords = cartographic_radians_to_coords(radians)
                
                # Simplify
                simplified_coords = simplify_polyline(coords, tolerance)
                simplified_points += len(simplified_coords)
                
                # Convert back to radians
                simplified_radians = coords_to_cartographic_radians(simplified_coords)
                
                # Update packet
                packet['polyline']['positions']['cartographicRadians'] = simplified_radians
        
        if i % 1000 == 0:
            print(f"Processed {i}/{total_polylines} polylines...")
    
    # Write optimized CZML
    print("\nWriting optimized CZML...")
    with open(output_file, 'w') as f:
        json.dump(czml_data, f, separators=(',', ':'))
    
    # Statistics
    optimized_size = os.path.getsize(output_file) / (1024 * 1024)
    reduction = ((original_size - optimized_size) / original_size) * 100
    point_reduction = ((original_points - simplified_points) / original_points) * 100
    
    print(f"\n{'='*60}")
    print("OPTIMIZATION COMPLETE")
    print(f"{'='*60}")
    print(f"Original size:     {original_size:.1f} MB")
    print(f"Optimized size:    {optimized_size:.1f} MB")
    print(f"Size reduction:    {reduction:.1f}%")
    print(f"\nOriginal points:   {original_points:,}")
    print(f"Optimized points:  {simplified_points:,}")
    print(f"Point reduction:   {point_reduction:.1f}%")
    print(f"\nPolylines:         {total_polylines}")
    print(f"Avg points/line:   {simplified_points/total_polylines:.1f}")
    
    return {
        'original_size_mb': original_size,
        'optimized_size_mb': optimized_size,
        'reduction_percent': reduction,
        'original_points': original_points,
        'optimized_points': simplified_points,
        'point_reduction_percent': point_reduction
    }

def main():
    print("="*60)
    print("CZML OPTIMIZATION TOOL")
    print("Simplify polylines while maintaining visual quality")
    print("="*60)
    
    # Define optimization levels
    optimizations = [
        {
            'input': 'states_provinces_10m.czml',
            'output': 'states_provinces_10m_optimized.czml',
            'tolerance': 0.00005,  # ~0.003 degrees, ~300m at equator
            'name': 'States and Provinces Borders 10m (Optimized)'
        },
        {
            'input': 'states_provinces_10m.czml',
            'output': 'states_provinces_10m_light.czml',
            'tolerance': 0.0001,   # ~0.006 degrees, ~600m at equator
            'name': 'States and Provinces Borders 10m (Light)'
        },
        {
            'input': 'states_provinces_10m.czml',
            'output': 'states_provinces_10m_ultralight.czml',
            'tolerance': 0.0002,   # ~0.011 degrees, ~1.2km at equator
            'name': 'States and Provinces Borders 10m (Ultra Light)'
        }
    ]
    
    results = []
    
    for opt in optimizations:
        if not os.path.exists(opt['input']):
            print(f"\nWARNING: Input file not found: {opt['input']}")
            continue
        
        result = optimize_czml(
            opt['input'],
            opt['output'],
            opt['tolerance'],
            opt['name']
        )
        result['output_file'] = opt['output']
        result['tolerance'] = opt['tolerance']
        results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("OPTIMIZATION SUMMARY")
    print("="*60)
    print(f"\n{'Version':<20} {'Size':<12} {'Reduction':<12} {'Points':<15}")
    print("-" * 60)
    
    for i, result in enumerate(results):
        version = ['Optimized', 'Light', 'Ultra Light'][i]
        print(f"{version:<20} {result['optimized_size_mb']:>6.1f} MB   "
              f"{result['reduction_percent']:>6.1f}%      "
              f"{result['optimized_points']:>10,}")
    
    print("\nRecommendations:")
    print("  • Optimized: Best balance (minimal visual difference)")
    print("  • Light: Good for most applications (slight simplification)")
    print("  • Ultra Light: Maximum performance (noticeable at high zoom)")

if __name__ == '__main__':
    main()