"""
Memory Operations - LLM reasoning and context storage
"""
from typing import Dict, List, Any


class MemoryOperations:
    """Handles all agent memory and LLM context operations"""

    def __init__(self, db_connection):
        """Initialize with database connection"""
        self.conn = db_connection

    def store_agent_memory(self, context_type: str, decision_context: str,
                          llm_reasoning: str, confidence_score: float = None,
                          product_code: str = None, supplier_id: int = None) -> int:
        """
        Store LLM reasoning and context for future reference

        Args:
            context_type: Type of decision (e.g., 'inventory_analysis', 'supplier_selection')
            decision_context: JSON string with context data
            llm_reasoning: The LLM's reasoning/output
            confidence_score: Optional confidence score (0-1)
            product_code: Optional product code
            supplier_id: Optional supplier ID

        Returns:
            memory_id: ID of the stored memory
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO agent_memory 
            (context_type, product_code, supplier_id, decision_context, 
             llm_reasoning, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (context_type, product_code, supplier_id, decision_context,
              llm_reasoning, confidence_score))
        self.conn.commit()

        return cursor.lastrowid

    def get_agent_memory(self, context_type: str = None, product_code: str = None,
                        supplier_id: int = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve relevant agent memory for context

        Args:
            context_type: Filter by context type
            product_code: Filter by product
            supplier_id: Filter by supplier
            limit: Maximum number of results

        Returns:
            List of memory records
        """
        cursor = self.conn.cursor()

        query = "SELECT * FROM agent_memory WHERE 1=1"
        params = []

        if context_type:
            query += " AND context_type = ?"
            params.append(context_type)
        if product_code:
            query += " AND product_code = ?"
            params.append(product_code)
        if supplier_id:
            query += " AND supplier_id = ?"
            params.append(supplier_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_memory_by_id(self, memory_id: int) -> Dict[str, Any]:
        """Get specific memory record by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM agent_memory WHERE memory_id = ?", (memory_id,))
        result = cursor.fetchone()
        return dict(result) if result else None

    def get_recent_decisions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most recent AI decisions across all types"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM agent_memory 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about stored memories"""
        cursor = self.conn.cursor()

        # Total memories
        cursor.execute("SELECT COUNT(*) as total FROM agent_memory")
        total = cursor.fetchone()['total']

        # By context type
        cursor.execute("""
            SELECT context_type, COUNT(*) as count 
            FROM agent_memory 
            GROUP BY context_type
        """)
        by_type = {row['context_type']: row['count'] for row in cursor.fetchall()}

        # Average confidence score
        cursor.execute("""
            SELECT AVG(confidence_score) as avg_confidence 
            FROM agent_memory 
            WHERE confidence_score IS NOT NULL
        """)
        avg_conf = cursor.fetchone()['avg_confidence']

        return {
            'total_memories': total,
            'by_context_type': by_type,
            'avg_confidence_score': avg_conf
        }

    def delete_old_memories(self, days: int = 90):
        """Delete memories older than specified days (for cleanup)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM agent_memory 
            WHERE created_at < datetime('now', '-' || ? || ' days')
        """, (days,))
        deleted = cursor.rowcount
        self.conn.commit()
        return {'deleted_count': deleted}

