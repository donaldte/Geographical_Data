import sys
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import pymongo
from typing import List, Dict, Any


def read_shapefile(shapefile_path: str) -> gpd.GeoDataFrame:
    """
    Read a shapefile using GeoPandas and sanitize date and float columns.

    :param shapefile_path: Path to the .shp file
    :return: A cleaned GeoDataFrame
    """
    if not shapefile_path.endswith('.shp'):
        raise ValueError("Please provide a valid .shp file path.")

    try:
        gdf = gpd.read_file(shapefile_path)

        # Handle date columns
        date_columns = ['creation_d', 'last_updat']
        for col in date_columns:
            if col in gdf.columns:
                gdf[col] = gdf[col].astype(str).replace('nan', '')

        # Convert float columns to string
        float_columns = ['district', 'county_fip', 'countynum', 'shape_Leng', 'shape_Area']
        for col in float_columns:
            if col in gdf.columns:
                gdf[col] = gdf[col].apply(lambda x: str(x) if pd.notnull(x) else '')

        # Display basic info
        print("Shapefile Information:")
        print(f"Total Features: {len(gdf)}")
        print(f"Columns: {list(gdf.columns)}")
        print(f"Coordinate Reference System (CRS): {gdf.crs}\n")
        print("First few rows:")
        print(gdf.head())

        return gdf

    except Exception as e:
        raise RuntimeError(f"Error reading shapefile: {e}")


def convert_to_geojson(gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
    """
    Convert a GeoDataFrame into a GeoJSON-like dictionary.

    :param gdf: The GeoDataFrame to convert
    :return: GeoJSON FeatureCollection as a dict
    """
    features: List[Dict[str, Any]] = []

    for _, row in gdf.iterrows():
        feature = {
            "type": "Feature",
            "geometry": row["geometry"].__geo_interface__,
            "properties": {
                col: str(row[col]) if pd.notnull(row[col]) else None
                for col in gdf.columns if col != "geometry"
            }
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features
    }


def insert_into_mongodb(geojson: Dict[str, Any], shapefile_path: str) -> None:
    """
    Insert GeoJSON features into MongoDB.

    :param geojson: GeoJSON object to insert
    :param shapefile_path: Used to determine which collection to use
    """
    try:
        client = pymongo.MongoClient("mongodb://localhost:27017/")

        # Determine database and collection based on filename
        if "InvasiveSpeciesExtremeConcernAreas_Watersheds" in shapefile_path:
            db = client["dc_watersheds"]
            collection = db["invasive_species"]
        else:
            db = client["maryland_counties"]
            collection = db["county_boundaries"]

        # Clear collection and insert new data
        collection.delete_many({})
        if geojson["features"]:
            collection.insert_many(geojson["features"])
            print(f"\n✅ Successfully inserted {len(geojson['features'])} documents into {db.name}.{collection.name}")
        else:
            print("⚠️ No features to insert.")

    except Exception as e:
        raise ConnectionError(f"Error inserting data into MongoDB: {e}")


def load_shapefile_to_mongodb(shapefile_path: str) -> None:
    """
    Complete flow: Load shapefile, convert to GeoJSON, and store in MongoDB.

    :param shapefile_path: Path to the shapefile
    """
    try:
        gdf = read_shapefile(shapefile_path)
        geojson = convert_to_geojson(gdf)
        insert_into_mongodb(geojson, shapefile_path)
    except Exception as err:
        print(f"❌ {err}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide the shapefile path as a command-line argument.")
        sys.exit(1)

    input_shapefile = sys.argv[1]
    load_shapefile_to_mongodb(input_shapefile)
