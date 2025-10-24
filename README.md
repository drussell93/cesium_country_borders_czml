# Angular Usage

## Using the CZML files
Place the CZML files in your assets directory and load into Cesium as follows:
```typescript
const bordersPromise = Cesium.CzmlDataSource.load('assets/imagery/borders/countryborders.czml');
bordersPromise.then(function(dataSource) {
    viewer.dataSources.add(dataSource);
}).catch((err) => {
    console.error('Failed to load country borders CZML:', err);
});
```

### Note
The provided CZML files are not perfect. You can re-create the files and perform accuracy, optimization, and other improvements following the guide below:

# Shapefile to CZML Conversion Guide

## Complete Step-by-Step Process for Converting Natural Earth Shapefiles to Cesium CZML Format

This guide provides the exact process used to convert Natural Earth country border shapefiles (110m, 50m, and 10m resolutions) to accurate CZML format for use in Cesium applications.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Understanding the Problem](#understanding-the-problem)
3. [Source Data](#source-data)
4. [Conversion Process](#conversion-process)
5. [Python Script](#python-script)
6. [Validation](#validation)
7. [Results](#results)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

1. **Python 3.7+**
   ```bash
   python3 --version
   ```

2. **Required Python Libraries**
   ```bash
   pip install pyshp
   ```
   
   Or if you need to install:
   ```bash
   pip install pyshp shapely
   ```

### Required Files

Download Natural Earth shapefiles from [Natural Earth Data](https://www.naturalearthdata.com/downloads/):

---

## Understanding the Problem

### Why Not Just Convert Directly?

When converting shapefiles to CZML, you might encounter these issues:

1. **Random Connecting Lines**: If polygon parts aren't properly closed, you'll see lines connecting separate regions
2. **Multi-part Polygons**: Countries with islands (Indonesia, USA, etc.) have multiple polygon parts that need separate handling
3. **File Size**: Raw conversion creates very large files that need optimization
4. **Coordinate Format**: Cesium requires radians, not decimal degrees

### The Solution

Our conversion process:
1. Treats each polygon part as a separate entity
2. Properly closes each polygon (first point = last point)
3. Applies smart simplification to reduce file size
4. Converts coordinates to radians
5. Validates all output

---

## Source Data

### Natural Earth Shapefiles

Each shapefile package contains:
- `.shp` - Shape geometry
- `.shx` - Shape index
- `.dbf` - Attribute data (country names, etc.)
- `.prj` - Projection information
- `.cpg` - Character encoding

### Shapefile Structure

```
ne_10m_admin_0_countries/
├── ne_10m_admin_0_countries.shp
├── ne_10m_admin_0_countries.shx
├── ne_10m_admin_0_countries.dbf
├── ne_10m_admin_0_countries.prj
└── ne_10m_admin_0_countries.cpg
```

---

## Conversion Process

### Step 1: Extract Shapefiles

```bash
# Extract all three resolutions
unzip ne_110m_admin_0_countries.zip
unzip ne_50m_admin_0_countries.zip
unzip ne_10m_admin_0_countries.zip
```

### Step 2: Create the Conversion Script

Create a file named `shapefile_to_czml.py` with the following content:

```python
import shapefile
import json
import math

def lon_lat_to_radians(lon, lat):
    """Convert longitude and latitude from degrees to radians"""
    return math.radians(lon), math.radians(lat)

def rdp_simplify(points, epsilon):
    """
    Ramer-Douglas-Peucker line simplification algorithm.
    Reduces the number of points while preserving shape.
    
    Args:
        points: List of (x, y) coordinate tuples
        epsilon: Tolerance for simplification (higher = more simplification)
    
    Returns:
        Simplified list of points
    """
    if len(points) < 3:
        return points
    
    dmax = 0
    index = 0
    end = len(points) - 1
    
    # Find the point with maximum distance from line
    for i in range(1, end):
        d = point_line_distance(points[i], points[0], points[end])
        if d > dmax:
            index = i
            dmax = d
    
    # If max distance is greater than epsilon, recursively simplify
    if dmax > epsilon:
        rec1 = rdp_simplify(points[:index+1], epsilon)
        rec2 = rdp_simplify(points[index:], epsilon)
        result = rec1[:-1] + rec2
    else:
        result = [points[0], points[end]]
    
    return result

def point_line_distance(point, line_start, line_end):
    """Calculate perpendicular distance from point to line"""
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    dx = x2 - x1
    dy = y2 - y1
    
    if dx == 0 and dy == 0:
        return math.sqrt((x0 - x1)**2 + (y0 - y1)**2)
    
    numerator = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1)
    denominator = math.sqrt(dx**2 + dy**2)
    
    return numerator / denominator

def create_czml_from_shapefile(shapefile_path, output_path, base_epsilon=0.01):
    """
    Convert shapefile to CZML with proper polygon handling.
    
    Args:
        shapefile_path: Path to shapefile (without extension)
        output_path: Output CZML file path
        base_epsilon: Base tolerance for simplification
    
    Returns:
        Tuple of (entity_count, total_points)
    """
    
    # Read the shapefile
    sf = shapefile.Reader(shapefile_path)
    
    # Initialize CZML with document header
    czml = [{"id": "document", "version": "1.0"}]
    
    print(f"Processing {len(sf.shapes())} shapes from {shapefile_path}...")
    
    entity_count = 0
    total_points_before = 0
    total_points_after = 0
    
    # Process each shape (country)
    for shape_idx, (shape, record) in enumerate(zip(sf.shapes(), sf.records())):
        # Get country name from attributes
        try:
            name_idx = [field[0] for field in sf.fields[1:]].index('NAME')
            country_name = record[name_idx]
        except (ValueError, IndexError):
            try:
                admin_idx = [field[0] for field in sf.fields[1:]].index('ADMIN')
                country_name = record[admin_idx]
            except (ValueError, IndexError):
                country_name = f"Country_{shape_idx}"
        
        if not shape.points:
            continue
        
        # Process each polygon part separately
        # This is CRITICAL to avoid random connecting lines
        for part_idx in range(len(shape.parts)):
            # Get start and end indices for this polygon part
            start = shape.parts[part_idx]
            end = shape.parts[part_idx + 1] if part_idx + 1 < len(shape.parts) else len(shape.points)
            
            # Extract points for this part
            part_points = shape.points[start:end]
            total_points_before += len(part_points)
            
            if len(part_points) < 2:
                continue
            
            # Apply adaptive simplification based on polygon size
            if len(part_points) > 1000:
                epsilon = base_epsilon * 2.0
            elif len(part_points) > 500:
                epsilon = base_epsilon * 1.5
            elif len(part_points) > 100:
                epsilon = base_epsilon
            else:
                epsilon = base_epsilon * 0.5
            
            # Simplify if polygon is large enough
            if len(part_points) > 20:
                part_points = rdp_simplify(part_points, epsilon)
            
            # CRITICAL: Close the polygon by ensuring first point = last point
            if len(part_points) >= 2 and part_points[0] != part_points[-1]:
                part_points.append(part_points[0])
            
            if len(part_points) < 2:
                continue
            
            # Convert to cartographic radians format
            cartographic_radians = []
            for point in part_points:
                lon_rad, lat_rad = lon_lat_to_radians(point[0], point[1])
                cartographic_radians.extend([lon_rad, lat_rad, 0.0])
            
            total_points_after += len(cartographic_radians) // 3
            
            # Create CZML entity for this polygon part
            entity = {
                "id": f"{country_name}_{shape_idx}_{part_idx}",
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
                }
            }
            
            # Add label only to the first part of each country
            if part_idx == 0:
                entity["label"] = {
                    "text": country_name
                }
            
            czml.append(entity)
            entity_count += 1
    
    # Write to file
    with open(output_path, 'w') as f:
        json.dump(czml, f)
    
    # Calculate statistics
    reduction = 100 * (1 - total_points_after / total_points_before) if total_points_before > 0 else 0
    
    print(f"  Entities created: {entity_count:,}")
    print(f"  Points before simplification: {total_points_before:,}")
    print(f"  Points after simplification: {total_points_after:,}")
    print(f"  Size reduction: {reduction:.1f}%")
    
    return entity_count, total_points_after

# Main execution
if __name__ == "__main__":
    print("=" * 70)
    print("SHAPEFILE TO CZML CONVERSION")
    print("=" * 70)
    
    # Convert 110m resolution (low detail, smallest file)
    print("\n110m Resolution (Low Detail):")
    print("-" * 70)
    entities_110m, points_110m = create_czml_from_shapefile(
        "ne_110m_admin_0_countries",
        "countryborders_110m.czml",
        base_epsilon=0.005  # Very light simplification
    )
    
    # Convert 50m resolution (medium detail)
    print("\n50m Resolution (Medium Detail):")
    print("-" * 70)
    entities_50m, points_50m = create_czml_from_shapefile(
        "ne_50m_admin_0_countries",
        "countryborders_50m.czml",
        base_epsilon=0.008  # Light simplification
    )
    
    # Convert 10m resolution (high detail, largest file)
    print("\n10m Resolution (High Detail):")
    print("-" * 70)
    entities_10m, points_10m = create_czml_from_shapefile(
        "ne_10m_admin_0_countries",
        "countryborders_10m.czml",
        base_epsilon=0.01  # Moderate simplification
    )
    
    # Summary
    print("\n" + "=" * 70)
    print("CONVERSION SUMMARY")
    print("=" * 70)
    
    print(f"\n110m Resolution:")
    print(f"  File: countryborders_110m.czml")
    print(f"  Entities: {entities_110m:,}")
    print(f"  Points: {points_110m:,}")
    
    print(f"\n50m Resolution:")
    print(f"  File: countryborders_50m.czml")
    print(f"  Entities: {entities_50m:,}")
    print(f"  Points: {points_50m:,}")
    
    print(f"\n10m Resolution:")
    print(f"  File: countryborders_10m.czml")
    print(f"  Entities: {entities_10m:,}")
    print(f"  Points: {points_10m:,}")
    
    print("\n" + "=" * 70)
    print("CONVERSION COMPLETE!")
    print("=" * 70)
```

### Step 3: Run the Conversion

```bash
python3 shapefile_to_czml.py
```

**Expected Output:**
```
======================================================================
SHAPEFILE TO CZML CONVERSION
======================================================================

110m Resolution (Low Detail):
----------------------------------------------------------------------
Processing 177 shapes from ne_110m_admin_0_countries...
  Entities created: 289
  Points before simplification: 10,654
  Points after simplification: 10,510
  Size reduction: 1.4%

50m Resolution (Medium Detail):
----------------------------------------------------------------------
Processing 242 shapes from ne_50m_admin_0_countries...
  Entities created: 1,632
  Points before simplification: 99,613
  Points after simplification: 75,060
  Size reduction: 24.6%

10m Resolution (High Detail):
----------------------------------------------------------------------
Processing 258 shapes from ne_10m_admin_0_countries...
  Entities created: 4,293
  Points before simplification: 548,471
  Points after simplification: 166,945
  Size reduction: 69.6%

======================================================================
CONVERSION SUMMARY
======================================================================

110m Resolution:
  File: countryborders_110m.czml
  Entities: 289
  Points: 10,510

50m Resolution:
  File: countryborders_50m.czml
  Entities: 1,632
  Points: 75,060

10m Resolution:
  File: countryborders_10m.czml
  Entities: 4,293
  Points: 166,945

======================================================================
CONVERSION COMPLETE!
======================================================================
```

---

## Validation

### Step 4: Create Validation Script

Create `validate_czml.py`:

```python
import json
import os

def validate_czml(filename):
    """Validate CZML file structure and content"""
    
    print(f"\nValidating {filename}:")
    print("-" * 70)
    
    try:
        with open(filename, 'r') as f:
            czml = json.load(f)
        
        print(f"✓ Valid JSON")
        print(f"✓ Total items: {len(czml):,}")
        print(f"✓ Entities: {len(czml) - 1:,}")
        
        # Validate document header
        if czml[0].get('id') == 'document' and czml[0].get('version'):
            print(f"✓ Valid document header")
        else:
            print(f"✗ Invalid document header")
            return False
        
        # Validate coordinates
        invalid = 0
        for item in czml[1:]:
            if 'polyline' in item:
                coords = item['polyline']['positions']['cartographicRadians']
                if len(coords) < 3 or len(coords) % 3 != 0:
                    invalid += 1
        
        if invalid == 0:
            print(f"✓ All coordinates valid (multiples of 3, >= 3)")
        else:
            print(f"✗ {invalid} invalid coordinate arrays")
            return False
        
        # Count labels
        labels = sum(1 for item in czml[1:] if 'label' in item)
        print(f"✓ Countries with labels: {labels}")
        
        # Check clampToGround
        clamped = sum(1 for item in czml[1:] if 'polyline' in item and item['polyline'].get('clampToGround'))
        print(f"✓ Entities with clampToGround: {clamped}")
        
        # File size
        size_mb = os.path.getsize(filename) / (1024 * 1024)
        if size_mb < 1:
            size_kb = os.path.getsize(filename) / 1024
            print(f"✓ File size: {size_kb:.1f} KB")
        else:
            print(f"✓ File size: {size_mb:.2f} MB")
        
        # Sample countries
        print(f"\nSample countries:")
        shown = 0
        for item in czml[1:]:
            if 'label' in item and shown < 5:
                points = len(item['polyline']['positions']['cartographicRadians']) // 3
                print(f"  {item['label']['text']}: {points} points")
                shown += 1
        
        print(f"\n✓ VALIDATION PASSED")
        return True
        
    except Exception as e:
        print(f"✗ VALIDATION FAILED: {e}")
        return False

# Main execution
if __name__ == "__main__":
    print("=" * 70)
    print("CZML VALIDATION")
    print("=" * 70)
    
    files = [
        'countryborders_110m.czml',
        'countryborders_50m.czml',
        'countryborders_10m.czml'
    ]
    
    all_valid = True
    for filename in files:
        if os.path.exists(filename):
            if not validate_czml(filename):
                all_valid = False
        else:
            print(f"\n✗ File not found: {filename}")
            all_valid = False
    
    print("\n" + "=" * 70)
    if all_valid:
        print("ALL FILES VALIDATED SUCCESSFULLY!")
    else:
        print("VALIDATION FAILED - CHECK ERRORS ABOVE")
    print("=" * 70)
```

### Step 5: Run Validation

```bash
python3 validate_czml.py
```

**Expected Output:**
```
======================================================================
CZML VALIDATION
======================================================================

Validating countryborders_110m.czml:
----------------------------------------------------------------------
✓ Valid JSON
✓ Total items: 290
✓ Entities: 289
✓ Valid document header
✓ All coordinates valid (multiples of 3, >= 3)
✓ Countries with labels: 177
✓ Entities with clampToGround: 289
✓ File size: 528.0 KB

Sample countries:
  Fiji: 8 points
  Tanzania: 48 points
  W. Sahara: 28 points
  Canada: 257 points
  United States of America: 216 points

✓ VALIDATION PASSED

Validating countryborders_50m.czml:
----------------------------------------------------------------------
✓ Valid JSON
✓ Total items: 1,633
✓ Entities: 1,632
✓ Valid document header
✓ All coordinates valid (multiples of 3, >= 3)
✓ Countries with labels: 242
✓ Entities with clampToGround: 1632
✓ File size: 3.57 MB

Sample countries:
  Zimbabwe: 123 points
  Zambia: 231 points
  Yemen: 124 points
  Vietnam: 13 points
  Venezuela: 11 points

✓ VALIDATION PASSED

Validating countryborders_10m.czml:
----------------------------------------------------------------------
✓ Valid JSON
✓ Total items: 4,294
✓ Entities: 4,293
✓ Valid document header
✓ All coordinates valid (multiples of 3, >= 3)
✓ Countries with labels: 258
✓ Entities with clampToGround: 4293
✓ File size: 8.06 MB

Sample countries:
  Indonesia: 17 points
  Malaysia: 11 points
  Chile: 1522 points
  Bolivia: 273 points
  Peru: 455 points

✓ VALIDATION PASSED

======================================================================
ALL FILES VALIDATED SUCCESSFULLY!
======================================================================
```

---

## Results

### Generated Files

After successful conversion, you'll have three CZML files:

```
countryborders_110m.czml  (528 KB)   - Low resolution, fastest loading
countryborders_50m.czml   (3.57 MB)  - Medium resolution, balanced
countryborders_10m.czml   (8.06 MB)  - High resolution, most detail
```

### File Specifications

| File | Size | Entities | Points | Countries |
|------|------|----------|--------|-----------|
| 110m | 528 KB | 289 | 10,510 | 177 |
| 50m | 3.57 MB | 1,632 | 75,060 | 242 |
| 10m | 8.06 MB | 4,293 | 166,945 | 258 |

---

## Key Technical Details

### Why Multiple Entities Per Country?

Countries with complex borders (islands, enclaves) have multiple polygon parts. Each part must be a separate closed polyline to avoid connecting lines:

**Example - Indonesia:**
- Main islands: Java, Sumatra, Borneo, etc.
- Each island is a separate polygon part
- Each part becomes a separate CZML entity
- Only the first part gets a label

### Coordinate Format

**Input (Shapefile):**
- Format: Decimal degrees
- Example: longitude = 120.5, latitude = 35.2

**Output (CZML):**
- Format: Radians
- Conversion: radians = degrees × π / 180
- Example: lon_rad = 2.103, lat_rad = 0.614
- Structure: [lon_rad, lat_rad, height, lon_rad, lat_rad, height, ...]

### Polygon Closing

**Critical for avoiding random lines:**
```python
# Before closing
points = [(120.5, 35.2), (121.0, 35.5), (120.8, 36.0)]

# After closing
points = [(120.5, 35.2), (121.0, 35.5), (120.8, 36.0), (120.5, 35.2)]
#         ^                                              ^
#         First point                                    Same as first
```

### Simplification Algorithm

**Ramer-Douglas-Peucker (RDP):**
1. Finds the point farthest from the line connecting start and end
2. If distance > epsilon, recursively simplify both segments
3. If distance ≤ epsilon, remove all intermediate points
4. Preserves overall shape while reducing point count

**Epsilon Values Used:**
- 110m: 0.005 (very light, already low resolution)
- 50m: 0.008 (light simplification)
- 10m: 0.01 (moderate simplification)

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'shapefile'"

**Solution:**
```bash
pip install pyshp
```

### Issue: Random Lines Between Countries

**Cause:** Polygons not properly closed

**Solution:** Ensure this code is in your script:
```python
if len(part_points) >= 2 and part_points[0] != part_points[-1]:
    part_points.append(part_points[0])
```

### Issue: "Invalid coordinate arrays"

**Cause:** Coordinate count not multiple of 3

**Solution:** Each point needs 3 values (lon, lat, height):
```python
cartographic_radians.extend([lon_rad, lat_rad, 0.0])
```

### Issue: File Too Large

**Solution:** Increase epsilon for more aggressive simplification:
```python
base_epsilon=0.02  # Instead of 0.01
```

### Issue: Too Much Detail Lost

**Solution:** Decrease epsilon for less simplification:
```python
base_epsilon=0.005  # Instead of 0.01
```

### Issue: Missing Countries

**Cause:** Shapefile field name different

**Solution:** Check field names:
```python
sf = shapefile.Reader("your_shapefile")
print([field[0] for field in sf.fields[1:]])
```

---

## Advanced Customization

### Change Border Color

Modify the material section:
```python
"material": {
    "solidColor": {
        "color": {
            "rgba": [255, 0, 0, 255]  # Red instead of white
        }
    }
}
```

### Change Line Width

Modify the width property:
```python
"width": 2  # Thicker lines
```

### Disable Terrain Clamping

Remove or set to false:
```python
"clampToGround": False  # Lines won't follow terrain
```

### Add Custom Properties

Add to entity:
```python
entity["properties"] = {
    "population": record[pop_idx],
    "area": record[area_idx]
}
```

---

## Complete File Structure

After following this guide, your directory should look like:

```
project/
├── ne_110m_admin_0_countries.shp
├── ne_110m_admin_0_countries.shx
├── ne_110m_admin_0_countries.dbf
├── ne_110m_admin_0_countries.prj
├── ne_110m_admin_0_countries.cpg
├── ne_50m_admin_0_countries.shp
├── ne_50m_admin_0_countries.shx
├── ne_50m_admin_0_countries.dbf
├── ne_50m_admin_0_countries.prj
├── ne_50m_admin_0_countries.cpg
├── ne_10m_admin_0_countries.shp
├── ne_10m_admin_0_countries.shx
├── ne_10m_admin_0_countries.dbf
├── ne_10m_admin_0_countries.prj
├── ne_10m_admin_0_countries.cpg
├── shapefile_to_czml.py
├── validate_czml.py
├── countryborders_110m.czml  ← Generated
├── countryborders_50m.czml   ← Generated
└── countryborders_10m.czml   ← Generated
```

---
