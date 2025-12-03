"""
통계 분석 유틸리티 모듈
"""

import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from sklearn.linear_model import LinearRegression

from database.models import Expense


def parse_date(date_str: str) -> date:
    """
    날짜 문자열을 date 객체로 변환
    '2025-11-29T00:00:00' 형식도 처리 가능
    
    Args:
        date_str: 날짜 문자열 (YYYY-MM-DD 또는 YYYY-MM-DDTHH:MM:SS 형식)
        
    Returns:
        date 객체
    """
    if isinstance(date_str, date):
        return date_str
    
    if date_str is None:
        raise ValueError("날짜가 None입니다")
    
    date_str = str(date_str).strip()
    
    if not date_str:
        raise ValueError("빈 날짜 문자열입니다")
    
    # datetime 형식 (시간 포함) 처리
    if 'T' in date_str:
        # T로 분리하여 날짜 부분만 추출
        date_part = date_str.split('T')[0]
        try:
            return date.fromisoformat(date_part)
        except ValueError:
            # 추가 시도: datetime으로 파싱
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.date()
            except ValueError:
                # 마지막 시도: 공백 제거 후 재시도
                date_part = date_part.strip()
                return date.fromisoformat(date_part)
    
    # 공백이 있는 경우 (예: '2025-11-29 00:00:00')
    if ' ' in date_str:
        date_part = date_str.split(' ')[0]
        try:
            return date.fromisoformat(date_part)
        except ValueError:
            # datetime으로 시도
            try:
                dt = datetime.fromisoformat(date_str)
                return dt.date()
            except ValueError:
                return date.fromisoformat(date_part.strip())
    
    # 일반 날짜 형식 (YYYY-MM-DD)
    try:
        return date.fromisoformat(date_str)
    except ValueError as e:
        raise ValueError(f"날짜 형식을 파싱할 수 없습니다: '{date_str}' - {str(e)}")


def calculate_category_stats(expenses: List[Expense]) -> Dict[str, Dict]:
    """
    카테고리별 통계 계산
    
    Args:
        expenses: 지출 리스트
        
    Returns:
        카테고리별 통계 딕셔너리
    """
    if not expenses:
        return {}
    
    category_data = defaultdict(list)
    
    for expense in expenses:
        category_data[expense.category].append(expense.amount)
    
    stats = {}
    for category, amounts in category_data.items():
        stats[category] = {
            'total': sum(amounts),
            'count': len(amounts),
            'mean': np.mean(amounts),
            'median': np.median(amounts),
            'min': min(amounts),
            'max': max(amounts),
            'std': np.std(amounts) if len(amounts) > 1 else 0.0
        }
    
    return stats


def calculate_mom_growth(
    expenses: List[Expense],
    current_month: Optional[date] = None
) -> Dict[str, float]:
    """
    Month-on-Month 증감률 계산
    
    Args:
        expenses: 지출 리스트
        current_month: 현재 월 (None이면 오늘 날짜 기준)
        
    Returns:
        카테고리별 MoM 증감률 딕셔너리
    """
    if not expenses:
        return {}
    
    if current_month is None:
        current_month = date.today()
    
    # 현재 월과 전월 계산
    current_start = date(current_month.year, current_month.month, 1)
    if current_month.month == 1:
        prev_start = date(current_month.year - 1, 12, 1)
        prev_end = date(current_month.year - 1, 12, 31)
    else:
        prev_start = date(current_month.year, current_month.month - 1, 1)
        prev_end = date(current_month.year, current_month.month, 1) - timedelta(days=1)
    
    current_end = current_start + timedelta(days=32)
    current_end = date(current_end.year, current_end.month, 1) - timedelta(days=1)
    
    # 월별 카테고리별 합계 계산
    current_month_data = defaultdict(float)
    prev_month_data = defaultdict(float)
    
    for expense in expenses:
        exp_date = expense.date
        if exp_date is None:
            continue
        
        if prev_start <= exp_date <= prev_end:
            prev_month_data[expense.category] += expense.amount
        elif current_start <= exp_date <= current_end:
            current_month_data[expense.category] += expense.amount
    
    # MoM 증감률 계산
    mom_growth = {}
    all_categories = set(list(current_month_data.keys()) + list(prev_month_data.keys()))
    
    for category in all_categories:
        prev_total = prev_month_data.get(category, 0)
        current_total = current_month_data.get(category, 0)
        
        if prev_total == 0:
            if current_total > 0:
                mom_growth[category] = float('inf')  # 무한대 증가
            else:
                mom_growth[category] = 0.0
        else:
            mom_growth[category] = ((current_total - prev_total) / prev_total) * 100
    
    return mom_growth


def detect_outliers(expenses: List[Expense]) -> List[Dict]:
    """
    평균+2SD 이상의 이상치 탐지 (높은 이상치만 포함)
    
    Args:
        expenses: 지출 리스트
        
    Returns:
        이상치 지출 리스트 (딕셔너리 형태) - 평균+2SD보다 높은 지출만 포함
    """
    if not expenses:
        return []
    
    # 카테고리별 통계 계산
    category_stats = calculate_category_stats(expenses)
    
    outliers = []
    
    for expense in expenses:
        if expense.category not in category_stats:
            continue
        
        stats = category_stats[expense.category]
        threshold = stats['mean'] + 2 * stats['std']
        
        # 평균+2SD보다 높은 지출만 이상치로 포함 (낮은 이상치는 제외)
        if expense.amount > threshold:
            outliers.append({
                'id': expense.id,
                'date': expense.date.isoformat() if expense.date else None,
                'category': expense.category,
                'description': expense.description,
                'amount': expense.amount,
                'threshold': threshold,
                'mean': stats['mean'],
                'std': stats['std']
            })
    
    return outliers


def predict_monthly_expense(
    expenses: List[Expense],
    target_month: Optional[date] = None
) -> Dict[str, float]:
    """
    회귀 분석을 사용한 월 지출 예상
    
    Args:
        expenses: 지출 리스트
        target_month: 예측할 월 (None이면 현재 월)
        
    Returns:
        카테고리별 예상 월 지출 딕셔너리
    """
    if not expenses:
        return {}
    
    if target_month is None:
        target_month = date.today()
    
    # 월별 카테고리별 합계 계산
    monthly_data = defaultdict(lambda: defaultdict(float))
    
    for expense in expenses:
        if expense.date is None:
            continue
        
        month_key = (expense.date.year, expense.date.month)
        monthly_data[month_key][expense.category] += expense.amount
    
    if not monthly_data:
        return {}
    
    # 각 카테고리별로 회귀 분석 수행
    predictions = {}
    
    # 모든 카테고리 수집
    all_categories = set()
    for month_data in monthly_data.values():
        all_categories.update(month_data.keys())
    
    # 월을 숫자로 변환 (예: 2024-01 -> 0, 2024-02 -> 1, ...)
    min_year, min_month = min(monthly_data.keys())
    months_since_start = {}
    for (year, month), _ in monthly_data.items():
        months_since_start[(year, month)] = (year - min_year) * 12 + (month - min_month)
    
    for category in all_categories:
        # 해당 카테고리의 월별 데이터 수집
        X = []
        y = []
        
        for (year, month), month_data in monthly_data.items():
            if category in month_data:
                X.append([months_since_start[(year, month)]])
                y.append(month_data[category])
        
        if len(X) < 2:  # 최소 2개 데이터 포인트 필요
            # 데이터가 부족하면 평균 사용
            if len(y) > 0:
                predictions[category] = np.mean(y)
            continue
        
        X = np.array(X)
        y = np.array(y)
        
        try:
            # 선형 회귀 모델 학습
            model = LinearRegression()
            model.fit(X, y)
            
            # 목표 월까지의 월 수 계산
            target_months = (target_month.year - min_year) * 12 + (target_month.month - min_month)
            
            # 예측 수행
            prediction = model.predict([[target_months]])[0]
            predictions[category] = max(0, prediction)  # 음수 방지
        except Exception as e:
            # 회귀 분석 실패 시 평균 사용
            predictions[category] = np.mean(y) if len(y) > 0 else 0.0
    
    return predictions

