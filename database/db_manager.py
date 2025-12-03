"""
SQLite 데이터베이스 관리 클래스
"""

import sqlite3
from datetime import date, datetime
from typing import List, Optional
from pathlib import Path

from .models import Expense, CREATE_EXPENSES_TABLE
from utils.analysis_utils import parse_date


class DatabaseManager:
    """데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = "expenses.db"):
        """
        초기화
        
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """데이터베이스 연결 반환"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
        return conn
    
    def init_db(self):
        """데이터베이스 테이블 초기화"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(CREATE_EXPENSES_TABLE)
            
            # 기존 테이블에 merchant 컬럼이 없으면 추가 (마이그레이션)
            try:
                cursor.execute("SELECT merchant FROM expenses LIMIT 1")
            except sqlite3.OperationalError:
                # merchant 컬럼이 없으면 추가
                cursor.execute("ALTER TABLE expenses ADD COLUMN merchant TEXT")
            
            conn.commit()
        finally:
            conn.close()
    
    def add_expense(
        self,
        date: date,
        category: str,
        description: str,
        amount: float,
        merchant: Optional[str] = None
    ) -> int:
        """
        지출 추가
        
        Args:
            date: 지출 날짜
            category: 카테고리
            description: 지출 내역
            amount: 금액
            merchant: 지출처 (선택사항)
            
        Returns:
            생성된 지출의 ID
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO expenses (date, category, description, amount, merchant)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date.isoformat(), category, description, amount, merchant)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def get_expenses(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Expense]:
        """
        기간별 지출 조회
        
        Args:
            start_date: 시작 날짜 (None이면 제한 없음)
            end_date: 종료 날짜 (None이면 제한 없음)
            
        Returns:
            지출 리스트
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            if start_date and end_date:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    WHERE date >= ? AND date <= ?
                    ORDER BY date DESC
                    """,
                    (start_date.isoformat(), end_date.isoformat())
                )
            elif start_date:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    WHERE date >= ?
                    ORDER BY date DESC
                    """,
                    (start_date.isoformat(),)
                )
            elif end_date:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    WHERE date <= ?
                    ORDER BY date DESC
                    """,
                    (end_date.isoformat(),)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    ORDER BY date DESC
                    """
                )
            
            rows = cursor.fetchall()
            expenses = []
            for row in rows:
                # merchant 필드 안전하게 가져오기 (sqlite3.Row는 .get() 메서드가 없음)
                merchant_value = None
                try:
                    merchant_value = row['merchant']
                except (KeyError, IndexError):
                    merchant_value = None
                
                expenses.append(Expense(
                    id=row['id'],
                    date=parse_date(row['date']),
                    category=row['category'],
                    description=row['description'],
                    amount=row['amount'],
                    merchant=merchant_value,
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
                ))
            return expenses
        finally:
            conn.close()
    
    def get_all_expenses(self) -> List[Expense]:
        """
        전체 지출 조회
        
        Returns:
            지출 리스트
        """
        return self.get_expenses()
    
    def get_category_expenses(
        self,
        category: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Expense]:
        """
        카테고리별 지출 조회
        
        Args:
            category: 카테고리명
            start_date: 시작 날짜 (None이면 제한 없음)
            end_date: 종료 날짜 (None이면 제한 없음)
            
        Returns:
            지출 리스트
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            if start_date and end_date:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    WHERE category = ? AND date >= ? AND date <= ?
                    ORDER BY date DESC
                    """,
                    (category, start_date.isoformat(), end_date.isoformat())
                )
            elif start_date:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    WHERE category = ? AND date >= ?
                    ORDER BY date DESC
                    """,
                    (category, start_date.isoformat())
                )
            elif end_date:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    WHERE category = ? AND date <= ?
                    ORDER BY date DESC
                    """,
                    (category, end_date.isoformat())
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM expenses
                    WHERE category = ?
                    ORDER BY date DESC
                    """,
                    (category,)
                )
            
            rows = cursor.fetchall()
            expenses = []
            for row in rows:
                # merchant 필드 안전하게 가져오기 (sqlite3.Row는 .get() 메서드가 없음)
                merchant_value = None
                try:
                    merchant_value = row['merchant']
                except (KeyError, IndexError):
                    merchant_value = None
                
                expenses.append(Expense(
                    id=row['id'],
                    date=parse_date(row['date']),
                    category=row['category'],
                    description=row['description'],
                    amount=row['amount'],
                    merchant=merchant_value,
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
                ))
            return expenses
        finally:
            conn.close()
    
    def get_categories(self) -> List[str]:
        """
        모든 카테고리 목록 조회
        
        Returns:
            카테고리 리스트
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT category FROM expenses
                ORDER BY category
                """
            )
            rows = cursor.fetchall()
            return [row['category'] for row in rows]
        finally:
            conn.close()
    
    def update_expense(
        self,
        expense_id: int,
        date: Optional[date] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        amount: Optional[float] = None,
        merchant: Optional[str] = None
    ) -> bool:
        """
        지출 수정
        
        Args:
            expense_id: 지출 ID
            date: 지출 날짜 (선택사항)
            category: 카테고리 (선택사항)
            description: 지출 내역 (선택사항)
            amount: 금액 (선택사항)
            merchant: 지출처 (선택사항)
            
        Returns:
            수정 성공 여부
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # 업데이트할 필드만 동적으로 구성
            updates = []
            params = []
            
            if date is not None:
                updates.append("date = ?")
                params.append(date.isoformat())
            if category is not None:
                updates.append("category = ?")
                params.append(category)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if amount is not None:
                updates.append("amount = ?")
                params.append(amount)
            if merchant is not None:
                updates.append("merchant = ?")
                params.append(merchant)
            
            if not updates:
                return False
            
            params.append(expense_id)
            
            query = f"UPDATE expenses SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def delete_expense(self, expense_id: int) -> bool:
        """
        지출 삭제
        
        Args:
            expense_id: 지출 ID
            
        Returns:
            삭제 성공 여부
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def get_expense_by_id(self, expense_id: int) -> Optional[Expense]:
        """
        ID로 지출 조회
        
        Args:
            expense_id: 지출 ID
            
        Returns:
            Expense 객체 또는 None
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            merchant_value = None
            try:
                merchant_value = row['merchant']
            except (KeyError, IndexError):
                merchant_value = None
            
            return Expense(
                id=row['id'],
                date=parse_date(row['date']),
                category=row['category'],
                description=row['description'],
                amount=row['amount'],
                merchant=merchant_value,
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
            )
        finally:
            conn.close()

