"""
데이터베이스 모델 정의
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class Expense:
    """지출 데이터 모델"""
    id: Optional[int] = None
    date: Optional[date] = None
    category: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    merchant: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'category': self.category,
            'description': self.description,
            'amount': self.amount,
            'merchant': self.merchant,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Expense':
        """딕셔너리에서 생성"""
        # 순환 import 방지를 위해 함수 내부에서 import
        from utils.analysis_utils import parse_date
        
        return cls(
            id=data.get('id'),
            date=parse_date(data['date']) if data.get('date') else None,
            category=data.get('category'),
            description=data.get('description'),
            amount=data.get('amount'),
            merchant=data.get('merchant'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
        )


# SQLite 테이블 생성 쿼리
CREATE_EXPENSES_TABLE = """
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    merchant TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

