#!/usr/bin/env python3
"""
Database Cleanup Script: Purge Ghost Files from seed_files

Removes filenames from project.seed_files that have no corresponding IngestionRecord
in the ingestions collection. This fixes inconsistent state where files were added
via the deprecated /ingest/pdf endpoint but never persisted.

Usage:
    python scripts/purge_ghosts.py <project_id>
    OR
    PROJECT_ID=<uuid> python scripts/purge_ghosts.py
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arango import ArangoClient
from arango.exceptions import ArangoClientError, ArangoServerError
from shared.config import get_memory_url, get_arango_password, ARANGODB_DB, ARANGODB_USER


def get_db():
    """Connect to ArangoDB and return the database client."""
    try:
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        print(f"✅ Connected to ArangoDB: {get_memory_url()}/{ARANGODB_DB}")
        return db
    except ArangoClientError as e:
        print(f"❌ ArangoDB Client Error: {e}")
        sys.exit(1)
    except ArangoServerError as e:
        print(f"❌ ArangoDB Server Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ An unexpected error occurred during DB connection: {e}")
        sys.exit(1)


def purge_ghost_files(project_id: str, dry_run: bool = False) -> int:
    """
    Purge ghost files from project.seed_files array.
    
    Args:
        project_id: The project UUID (used as _key in projects collection).
        dry_run: If True, only report what would be removed without making changes.
    
    Returns:
        Number of ghost files removed (or would be removed in dry_run mode).
    """
    db = get_db()
    
    print(f"\n{'=' * 80}")
    print(f"Purging Ghost Files for Project: {project_id}")
    print(f"{'=' * 80}")
    print()
    
    # Step 1: Fetch Project
    print("Step 1: Fetching project...")
    try:
        projects_col = db.collection("projects")
        project_doc = projects_col.get(project_id)
        
        if not project_doc:
            print(f"❌ Project with ID '{project_id}' not found.")
            sys.exit(1)
        
        project_title = project_doc.get("title", "Untitled")
        seed_files = project_doc.get("seed_files", [])
        
        print(f"  ✅ Project found: {project_title}")
        print(f"  📁 Current seed_files count: {len(seed_files)}")
        if seed_files:
            print(f"  📋 Files in seed_files:")
            for idx, filename in enumerate(seed_files, 1):
                print(f"     {idx}. {filename}")
        else:
            print(f"  ℹ️  No files in seed_files array.")
            return 0
        
    except Exception as e:
        print(f"  ❌ Error fetching project: {e}")
        sys.exit(1)
    
    # Step 2: Identify Ghosts
    print(f"\nStep 2: Identifying ghost files...")
    try:
        if not db.has_collection("ingestions"):
            print(f"  ⚠️  Collection 'ingestions' does not exist.")
            print(f"  → All files in seed_files are considered ghost files.")
            valid_filenames = set()
        else:
            # Query all ingestion records for this project
            query = """
            FOR ing IN ingestions
            FILTER ing.project_id == @project_id
            RETURN ing.filename
            """
            
            cursor = db.aql.execute(query, bind_vars={"project_id": project_id})
            ingestion_filenames = list(cursor)
            valid_filenames = {f for f in ingestion_filenames if f}  # Filter out None/empty
            
            print(f"  ✅ Found {len(valid_filenames)} valid ingestion record(s) for this project:")
            for idx, filename in enumerate(sorted(valid_filenames), 1):
                print(f"     {idx}. {filename}")
        
        # Identify ghost files (files in seed_files but not in valid_filenames)
        ghost_files = [f for f in seed_files if f not in valid_filenames]
        
        print(f"\n  🔍 Ghost files identified: {len(ghost_files)}")
        if ghost_files:
            for idx, filename in enumerate(ghost_files, 1):
                print(f"     {idx}. {filename}")
        else:
            print(f"  ✅ No ghost files found. All files in seed_files have corresponding IngestionRecords.")
            return 0
        
    except Exception as e:
        print(f"  ❌ Error identifying ghost files: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 3: Purge (or dry-run)
    print(f"\nStep 3: {'[DRY RUN] Would purge' if dry_run else 'Purging'} ghost files...")
    try:
        if dry_run:
            print(f"  ℹ️  DRY RUN MODE: No changes will be made.")
            print(f"  → Would remove {len(ghost_files)} ghost file(s) from seed_files")
            return len(ghost_files)
        
        # Calculate new seed_files array (only valid files)
        new_seed_files = [f for f in seed_files if f in valid_filenames]
        
        # Update project with cleaned seed_files
        query = """
        FOR p IN projects
        FILTER p._key == @key
        UPDATE p WITH {
          seed_files: @new_seed_files
        } IN projects
        RETURN NEW
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                "key": project_id,
                "new_seed_files": new_seed_files
            }
        )
        
        result = list(cursor)
        if not result:
            print(f"  ❌ Failed to update project (no document returned)")
            sys.exit(1)
        
        updated_doc = result[0]
        updated_seed_files = updated_doc.get("seed_files", [])
        
        print(f"  ✅ Project updated successfully")
        print(f"  📁 New seed_files count: {len(updated_seed_files)}")
        if updated_seed_files:
            print(f"  📋 Remaining files in seed_files:")
            for idx, filename in enumerate(updated_seed_files, 1):
                print(f"     {idx}. {filename}")
        
        return len(ghost_files)
        
    except Exception as e:
        print(f"  ❌ Error purging ghost files: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Purge ghost files from project.seed_files array",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Purge ghost files for a project
  python scripts/purge_ghosts.py <project_id>
  
  # Dry run (see what would be removed)
  python scripts/purge_ghosts.py <project_id> --dry-run
  
  # Using environment variable
  PROJECT_ID=<uuid> python scripts/purge_ghosts.py
        """
    )
    parser.add_argument(
        "project_id",
        nargs="?",
        help="Project ID (UUID). Can also be set via PROJECT_ID environment variable."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without making changes"
    )
    
    args = parser.parse_args()
    
    # Get project ID from args or environment
    project_id = args.project_id or os.environ.get("PROJECT_ID")
    
    if not project_id:
        print("❌ Error: Project ID not provided.")
        print("   Usage: python scripts/purge_ghosts.py <project_id>")
        print("   Or: PROJECT_ID=<uuid> python scripts/purge_ghosts.py")
        sys.exit(1)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE: No changes will be made to the database.\n")
    
    try:
        removed_count = purge_ghost_files(project_id, dry_run=args.dry_run)
        
        print(f"\n{'=' * 80}")
        if args.dry_run:
            print(f"DRY RUN COMPLETE")
            print(f"  → Would remove {removed_count} ghost file(s)")
        else:
            print(f"PURGE COMPLETE")
            print(f"  ✅ Removed {removed_count} ghost file(s)")
            if removed_count > 0:
                print(f"  → Project seed_files array has been cleaned")
        print(f"{'=' * 80}\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

