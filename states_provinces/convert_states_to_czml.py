#!/usr/bin/env python3
"""
Convert Natural Earth states/provinces shapefiles to CZML format.
Processes 10m, 50m, and 110m resolutions.
"""

import json
import fiona
from shapely.geometry import shape
import math
import os
import sys

def convert_shapefile_to_czml(shapefile_path, output_czml_path, resolution_name):
    """
    Convert shapefile to CZML format with polylines.
    
    Args:
        shapefile_path: Path to input shapefile
        output_czml_path: Path to output CZML file
        resolution_name: Name of resolution (e.g., "10m", "50m", "110m")
    """
    print(f"\n{'='*60}")
    print(f"Converting {resolution_name} States/Provinces to CZML")
    print(f"{'='*60}")
    print(f"Reading shapefile: {shapefile_path}")
    
    # Initialize CZML document
    czml_data = [
        {
            "id": "document",
            "name": f"States and Provinces Borders {resolution_name}",
            "version": "1.0"
        }
    ]
    
    # Read shapefile
    try:
        with fiona.open(shapefile_path) as src:
            print(f"Found {len(src)} features")
            
            feature_count = 0
            polyline_count = 0
            
            for feature in src:
                feature_count += 1
                
                # Get properties
                props = feature['properties']
                name = props.get('name', props.get('NAME', f'Feature_{feature_count}'))
                admin = props.get('admin', props.get('ADMIN', 'Unknown'))
                
                # Get geometry
                geom = shape(feature['geometry'])
                
                # Handle different geometry types
                if geom.geom_type == 'Polygon':
                    coords_list = [geom.exterior.coords]
                elif geom.geom_type == 'MultiPolygon':
                    coords_list = [poly.exterior.coords for poly in geom.geoms]
                elif geom.geom_type == 'LineString':
                    coords_list = [geom.coords]
                elif geom.geom_type == 'MultiLineString':
                    coords_list = [line.coords for line in geom.geoms]
                else:
                    print(f"Skipping unsupported geometry type: {geom.geom_type}")
                    continue
                
                # Create CZML polylines for each coordinate list
                for idx, coords in enumerate(coords_list):
                    polyline_count += 1
                    
                    # Convert coordinates to cartographic radians
                    cartographic_radians = []
                    for lon, lat in coords:
                        lon_rad = math.radians(lon)
                        lat_rad = math.radians(lat)
                        cartographic_radians.extend([lon_rad, lat_rad, 0])
                    
                    # Create CZML packet
                    czml_packet = {
                        "id": f"{name}_{admin}_{feature_count}_{idx}",
                        "polyline": {
                            "positions": {
                                "cartographicRadians": cartographic_radians
                            },
                            "material": {
                                "solidColor": {
                                    "color": {
                                        "rgba": [255, 255, 255, 255]
                                    }
                                }
                            },
                            "width": 1,
                            "clampToGround": True
                        },
                        "label": {
                            "text": f"{name}, {admin}"
                        }
                    }
                    
                    czml_data.append(czml_packet)
                
                if feature_count % 100 == 0:
                    print(f"Processed {feature_count} features, {polyline_count} polylines...")
        
        print(f"\nTotal features processed: {feature_count}")
        print(f"Total polylines created: {polyline_count}")
        
        # Write CZML file
        print(f"\nWriting CZML to: {output_czml_path}")
        with open(output_czml_path, 'w') as f:
            json.dump(czml_data, f, separators=(',', ':'))
        
        # Get file size
        size_mb = os.path.getsize(output_czml_path) / (1024 * 1024)
        print(f"✓ CZML file created: {output_czml_path} ({size_mb:.1f} MB)")
        print(f"✓ Contains {len(czml_data)} packets ({len(czml_data)-1} polylines)")
        
        return {
            'resolution': resolution_name,
            'features': feature_count,
            'polylines': polyline_count,
            'size_mb': size_mb,
            'output_file': output_czml_path
        }
        
    except Exception as e:
        print(f"ERROR converting {resolution_name}: {e}")
        return None

def main():
    print("="*60)
    print("NATURAL EARTH STATES/PROVINCES TO CZML CONVERTER")
    print("Converting All Resolutions: 10m, 50m, 110m")
    print("="*60)
    
    # Define conversions
    conversions = [
        {
            'shapefile': 'ne_10m_admin_1_states_provinces.shp',
            'output': 'states_provinces_10m.czml',
            'resolution': '10m'
        },
        {
            'shapefile': 'ne_50m_admin_1_states_provinces.shp',
            'output': 'states_provinces_50m.czml',
            'resolution': '50m'
        },
        {
            'shapefile': 'ne_110m_admin_1_states_provinces.shp',
            'output': 'states_provinces_110m.czml',
            'resolution': '110m'
        }
    ]
    
    results = []
    
    # Convert each resolution
    for conv in conversions:
        if not os.path.exists(conv['shapefile']):
            print(f"\nWARNING: Shapefile not found: {conv['shapefile']}")
            continue
        
        result = convert_shapefile_to_czml(
            conv['shapefile'],
            conv['output'],
            conv['resolution']
        )
        
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("CONVERSION COMPLETE!")
    print("="*60)
    print("\nSummary:")
    print(f"{'Resolution':<12} {'Features':<10} {'Polylines':<10} {'Size':<10}")
    print("-" * 60)
    
    for result in results:
        print(f"{result['resolution']:<12} {result['features']:<10} {result['polylines']:<10} {result['size_mb']:.1f} MB")
    
    print("\nFiles created:")
    for result in results:
        print(f"  ✓ {result['output_file']}")

if __name__ == '__main__':
    main()