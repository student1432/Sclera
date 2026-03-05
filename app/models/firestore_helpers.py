"""
Firestore database helpers.
Provides common database operations and utilities.
"""

from firebase_config import db
from firebase_admin import firestore
from datetime import datetime
from typing import Dict, List, Optional, Any


def get_document(collection: str, document_id: str) -> Optional[Dict]:
    """
    Get a document from Firestore.
    
    Args:
        collection: Collection name
        document_id: Document ID
        
    Returns:
        Document data or None if not found
    """
    try:
        doc = db.collection(collection).document(document_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"Error getting document {document_id} from {collection}: {e}")
        return None


def set_document(collection: str, document_id: str, data: Dict, merge: bool = True) -> bool:
    """
    Set a document in Firestore.
    
    Args:
        collection: Collection name
        document_id: Document ID
        data: Document data
        merge: Whether to merge with existing data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        db.collection(collection).document(document_id).set(data, merge=merge)
        return True
    except Exception as e:
        print(f"Error setting document {document_id} in {collection}: {e}")
        return False


def update_document(collection: str, document_id: str, data: Dict) -> bool:
    """
    Update a document in Firestore.
    
    Args:
        collection: Collection name
        document_id: Document ID
        data: Data to update
        
    Returns:
        True if successful, False otherwise
    """
    try:
        db.collection(collection).document(document_id).update(data)
        return True
    except Exception as e:
        print(f"Error updating document {document_id} in {collection}: {e}")
        return False


def delete_document(collection: str, document_id: str) -> bool:
    """
    Delete a document from Firestore.
    
    Args:
        collection: Collection name
        document_id: Document ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        db.collection(collection).document(document_id).delete()
        return True
    except Exception as e:
        print(f"Error deleting document {document_id} from {collection}: {e}")
        return False


def query_collection(
    collection: str,
    filters: List[tuple] = None,
    order_by: str = None,
    direction: str = 'ASC',
    limit: int = None
) -> List[Dict]:
    """
    Query a collection with optional filters and ordering.
    
    Args:
        collection: Collection name
        filters: List of (field, operator, value) tuples
        order_by: Field to order by
        direction: 'ASC' or 'DESC'
        limit: Maximum number of results
        
    Returns:
        List of document data
    """
    try:
        query = db.collection(collection)
        
        # Apply filters
        if filters:
            for field, operator, value in filters:
                query = query.where(field, operator, value)
        
        # Apply ordering
        if order_by:
            direction_enum = firestore.DESCENDING if direction.upper() == 'DESC' else firestore.ASCENDING
            query = query.order_by(order_by, direction=direction_enum)
        
        # Apply limit
        if limit:
            query = query.limit(limit)
        
        # Execute query
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
        
    except Exception as e:
        print(f"Error querying collection {collection}: {e}")
        return []


def get_subcollection(
    collection: str,
    document_id: str,
    subcollection: str,
    filters: List[tuple] = None,
    order_by: str = None,
    direction: str = 'ASC',
    limit: int = None
) -> List[Dict]:
    """
    Get documents from a subcollection.
    
    Args:
        collection: Parent collection name
        document_id: Parent document ID
        subcollection: Subcollection name
        filters: List of (field, operator, value) tuples
        order_by: Field to order by
        direction: 'ASC' or 'DESC'
        limit: Maximum number of results
        
    Returns:
        List of subcollection document data
    """
    try:
        query = db.collection(collection).document(document_id).collection(subcollection)
        
        # Apply filters
        if filters:
            for field, operator, value in filters:
                query = query.where(field, operator, value)
        
        # Apply ordering
        if order_by:
            direction_enum = firestore.DESCENDING if direction.upper() == 'DESC' else firestore.ASCENDING
            query = query.order_by(order_by, direction=direction_enum)
        
        # Apply limit
        if limit:
            query = query.limit(limit)
        
        # Execute query
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
        
    except Exception as e:
        print(f"Error getting subcollection {subcollection} from {collection}/{document_id}: {e}")
        return []


def add_to_subcollection(
    collection: str,
    document_id: str,
    subcollection: str,
    data: Dict
) -> Optional[str]:
    """
    Add a document to a subcollection.
    
    Args:
        collection: Parent collection name
        document_id: Parent document ID
        subcollection: Subcollection name
        data: Document data
        
    Returns:
        New document ID or None if failed
    """
    try:
        doc_ref = db.collection(collection).document(document_id).collection(subcollection).add(data)
        return doc_ref.id
    except Exception as e:
        print(f"Error adding document to subcollection {subcollection}: {e}")
        return None


def batch_operations(operations: List[tuple]) -> bool:
    """
    Execute multiple Firestore operations in a batch.
    
    Args:
        operations: List of tuples (operation_type, collection, document_id, data)
                   operation_type: 'set', 'update', 'delete'
        
    Returns:
        True if successful, False otherwise
    """
    try:
        batch = db.batch()
        
        for op_type, collection, doc_id, data in operations:
            doc_ref = db.collection(collection).document(doc_id)
            
            if op_type == 'set':
                batch.set(doc_ref, data)
            elif op_type == 'update':
                batch.update(doc_ref, data)
            elif op_type == 'delete':
                batch.delete(doc_ref)
        
        batch.commit()
        return True
        
    except Exception as e:
        print(f"Error executing batch operations: {e}")
        return False


def increment_field(collection: str, document_id: str, field: str, increment: int = 1) -> bool:
    """
    Increment a numeric field in a document.
    
    Args:
        collection: Collection name
        document_id: Document ID
        field: Field name to increment
        increment: Increment value (default: 1)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        db.collection(collection).document(document_id).update({
            field: firestore.Increment(increment)
        })
        return True
    except Exception as e:
        print(f"Error incrementing field {field} in {collection}/{document_id}: {e}")
        return False


def get_timestamp() -> str:
    """
    Get current timestamp in ISO format.
    
    Returns:
        ISO format timestamp string
    """
    return datetime.utcnow().isoformat()


def parse_timestamp(timestamp: str) -> Optional[datetime]:
    """
    Parse ISO timestamp string to datetime object.
    
    Args:
        timestamp: ISO format timestamp string
        
    Returns:
        datetime object or None if parsing fails
    """
    try:
        return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except Exception as e:
        print(f"Error parsing timestamp {timestamp}: {e}")
        return None
