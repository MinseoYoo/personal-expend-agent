"""
지출 분석 서비스 메인 비즈니스 로직 모듈
에이전트와 유틸의 기능을 모두 처리하는 서비스 레이어
"""

from datetime import date, datetime
from typing import Optional, Tuple
import pandas as pd
import plotly.graph_objects as go
from io import StringIO
import gc
import time
import traceback
import sys
import asyncio
import os

# Windows에서 asyncio 이벤트 루프 정책 설정 (모듈 로드 시 즉시 실행)
if sys.platform == 'win32':
    try:
        # 기존 루프 정리
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.close()
        except (RuntimeError, AttributeError):
            pass
        
        # WindowsSelectorEventLoopPolicy 설정
        if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # Gradio 관련 환경 변수 설정
        os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')
    except Exception as e:
        print(f"이벤트 루프 정책 설정 경고: {e}")

from database.db_manager import DatabaseManager
from agents.db_agent import DBAgent
from agents.analysis_agent import AnalysisAgent
from agents.report_agent import ReportAgent
from utils.llm_utils import CategoryClassifier
from utils.analysis_utils import (
    calculate_category_stats,
    calculate_mom_growth,
    detect_outliers,
    predict_monthly_expense,
    parse_date
)


# 전역 변수
db_manager = None
db_agent = None
analysis_agent = None
report_agent = None
category_classifier = None
user_name = ""  # 사용자 이름


def initialize_agents():
    """Agent 초기화"""
    global db_manager, db_agent, analysis_agent, report_agent, category_classifier
    
    db_manager = DatabaseManager()
    db_agent = DBAgent(db_manager)
    analysis_agent = AnalysisAgent(db_manager)
    report_agent = ReportAgent(db_manager, analysis_agent)
    category_classifier = CategoryClassifier()




def add_expense(
    expense_date: str,
    category: str,
    description: str,
    amount: float,
    merchant: str
) -> Tuple[str, str, str, str, str, str]:
    """
    지출 추가 비즈니스 로직
    
    Returns:
        (성공 메시지, 날짜 초기화, 카테고리 초기화, 설명 초기화, 금액 초기화, 지출처 초기화)
    """
    try:
        global db_manager, category_classifier
        
        # Agent 초기화 확인
        if db_manager is None or category_classifier is None:
            initialize_agents()
        
        if not expense_date:
            return "날짜를 입력해주세요.", expense_date, category, description, amount, merchant
        
        if not description or not description.strip():
            return "지출 내역을 입력해주세요.", expense_date, category, description, amount, merchant
        
        if not amount or amount <= 0:
            return "올바른 금액을 입력해주세요.", expense_date, category, description, amount, merchant
        
        # 날짜 형식 확인
        try:
            date_obj = parse_date(expense_date)
        except (ValueError, TypeError) as e:
            return f"날짜 형식이 올바르지 않습니다: {str(e)}", expense_date, category, description, amount, merchant
        
        # 카테고리가 없으면 자동 분류
        final_category = category.strip() if category and category.strip() else None
        final_merchant = merchant.strip() if merchant and merchant.strip() else None
        
        # DB에 추가
        expense_id = db_manager.add_expense(
            date=date_obj,
            category=final_category if final_category else category_classifier.classify(description),
            description=description,
            amount=amount,
            merchant=final_merchant
        )
        
        result = f"지출이 성공적으로 추가되었습니다. ID: {expense_id}"
        if final_category:
            result += f", 카테고리: {final_category}"
        
        return result, date.today().isoformat(), "", "", 0.0, ""
    except Exception as e:
        return f"오류 발생: {str(e)}", expense_date, category, description, amount, merchant


def upload_csv(csv_file) -> Tuple[str, pd.DataFrame]:
    """
    CSV 파일을 업로드하여 지출 데이터를 일괄 추가
    
    Args:
        csv_file: 업로드된 CSV 파일 경로
        
    Returns:
        (처리 결과 메시지, 업데이트된 표)
    """
    try:
        global db_manager, category_classifier
        
        # Agent 초기화 확인
        if db_manager is None or category_classifier is None:
            initialize_agents()
        
        if csv_file is None:
            return "CSV 파일을 선택해주세요.", get_expenses_table()
        
        # Gradio 버전에 따라 파일 경로 처리
        if isinstance(csv_file, str):
            file_path = csv_file
        elif hasattr(csv_file, 'name'):
            file_path = csv_file.name
        elif hasattr(csv_file, 'file_path'):
            file_path = csv_file.file_path
        else:
            file_path = str(csv_file)
        
        # CSV 파일 읽기 (Windows 권한 오류 해결)
        file_content = None
        file_handle = None
        try:
            file_handle = open(file_path, 'rb')
            file_content = file_handle.read()
        finally:
            if file_handle is not None:
                file_handle.close()
                file_handle = None
            gc.collect()
            time.sleep(0.1)
        
        # 메모리에서 인코딩 감지 및 디코딩
        if file_content.startswith(b'\xef\xbb\xbf'):
            content_str = file_content[3:].decode('utf-8')
        else:
            try:
                content_str = file_content.decode('utf-8-sig')
            except UnicodeDecodeError:
                try:
                    content_str = file_content.decode('cp949')
                except UnicodeDecodeError:
                    content_str = file_content.decode('utf-8', errors='ignore')
        
        file_content = None
        gc.collect()
        
        # 메모리에서 DataFrame 생성
        df = pd.read_csv(StringIO(content_str))
        
        # 필수 컬럼 확인
        required_columns = ['date', 'description', 'amount']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return f"CSV 파일에 필수 컬럼이 없습니다: {', '.join(missing_columns)}\n필수 컬럼: date, description, amount\n선택 컬럼: category, merchant", get_expenses_table()
        
        success_count = 0
        error_count = 0
        error_messages = []
        
        # 각 행 처리
        for idx, row in df.iterrows():
            try:
                # 날짜 파싱
                date_str = str(row['date']).strip()
                try:
                    if isinstance(row['date'], pd.Timestamp):
                        expense_date = row['date'].date()
                    else:
                        expense_date = parse_date(date_str)
                except (ValueError, AttributeError) as e:
                    error_count += 1
                    error_messages.append(f"행 {idx+1}: 날짜 형식 오류 ({date_str}): {str(e)}")
                    continue
                
                # 필수 필드 확인
                description = str(row['description']).strip()
                if not description:
                    error_count += 1
                    error_messages.append(f"행 {idx+1}: 지출 내역이 비어있습니다.")
                    continue
                
                amount = float(row['amount'])
                if amount <= 0:
                    error_count += 1
                    error_messages.append(f"행 {idx+1}: 금액이 0 이하입니다.")
                    continue
                
                # 선택 필드
                category = str(row.get('category', '')).strip() if 'category' in df.columns else None
                merchant = str(row.get('merchant', '')).strip() if 'merchant' in df.columns else None
                
                # 카테고리가 없으면 자동 분류
                if not category:
                    category = category_classifier.classify(description)
                
                # DB에 추가
                db_manager.add_expense(
                    date=expense_date,
                    category=category,
                    description=description,
                    amount=amount,
                    merchant=merchant if merchant else None
                )
                success_count += 1
            
            except Exception as e:
                error_count += 1
                error_messages.append(f"행 {idx+1}: {str(e)}")
        
        # 결과 메시지 생성
        result = f"CSV 파일 처리 완료!\n"
        result += f"✅ 성공: {success_count}건\n"
        if error_count > 0:
            result += f"❌ 실패: {error_count}건\n\n"
            result += "오류 상세:\n" + "\n".join(error_messages[:10])
            if len(error_messages) > 10:
                result += f"\n... 외 {len(error_messages) - 10}개 오류"
        else:
            result += "❌ 실패: 0건"
        
        updated_table = get_expenses_table()
        return result, updated_table
        
    except Exception as e:
        error_msg = f"CSV 파일 처리 중 오류 발생: {str(e)}\n\n상세:\n{traceback.format_exc()}"
        return error_msg, get_expenses_table()


def get_expenses_table() -> pd.DataFrame:
    """
    지출 내역을 표 형식으로 반환
    
    Returns:
        pandas DataFrame
    """
    try:
        global db_manager
        
        # Agent 초기화 확인
        if db_manager is None:
            initialize_agents()
        
        expenses = db_manager.get_all_expenses()
        if not expenses:
            return pd.DataFrame(columns=['ID', '날짜', '카테고리', '지출 내역', '금액', '지출처', '삭제'])
        
        # DataFrame 생성
        data = []
        for exp in expenses:
            data.append({
                'ID': exp.id,
                '날짜': exp.date.isoformat() if exp.date else '',
                '카테고리': exp.category or '',
                '지출 내역': exp.description or '',
                '금액': exp.amount if exp.amount else 0,
                '지출처': exp.merchant or '',
                '삭제': False  # 삭제 체크박스용
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame({'오류': [str(e)]})


def save_table_changes(edited_table: pd.DataFrame) -> Tuple[str, pd.DataFrame]:
    """
    표에서 수정된 내용을 DB에 저장 및 삭제 처리
    
    Args:
        edited_table: 편집된 DataFrame
        
    Returns:
        (결과 메시지, 업데이트된 표)
    """
    try:
        global db_manager, category_classifier
        
        # Agent 초기화 확인
        if db_manager is None or category_classifier is None:
            initialize_agents()
        
        if edited_table is None or edited_table.empty:
            return "저장할 데이터가 없습니다.", get_expenses_table()
        
        success_count = 0
        delete_count = 0
        error_count = 0
        error_messages = []
        
        # 삭제할 항목 먼저 처리
        delete_ids = []
        for idx, row in edited_table.iterrows():
            try:
                # 삭제 컬럼이 있고 True인 경우
                if '삭제' in row and (row['삭제'] is True or str(row['삭제']).lower() == 'true'):
                    expense_id = int(row['ID'])
                    delete_ids.append(expense_id)
            except Exception:
                pass
        
        # 삭제 실행
        for expense_id in delete_ids:
            try:
                success = db_manager.delete_expense(expense_id)
                if success:
                    delete_count += 1
                else:
                    error_count += 1
                    error_messages.append(f"지출(ID: {expense_id}) 삭제 실패: 찾을 수 없습니다.")
            except Exception as e:
                error_count += 1
                error_messages.append(f"지출(ID: {expense_id}) 삭제 중 오류: {str(e)}")
        
        # 삭제된 행 제외하고 업데이트 처리
        updated_table = edited_table[~edited_table['ID'].isin(delete_ids)].copy() if delete_ids else edited_table.copy()
        
        # 각 행 처리 (수정)
        for idx, row in updated_table.iterrows():
            try:
                expense_id = int(row['ID'])
                
                # 날짜 파싱
                date_str = str(row['날짜']).strip()
                try:
                    expense_date = parse_date(date_str)
                except (ValueError, AttributeError) as e:
                    error_count += 1
                    error_messages.append(f"행 {idx+1}: 날짜 형식 오류 ({date_str}): {str(e)}")
                    continue
                
                # 필수 필드 확인
                description = str(row['지출 내역']).strip()
                if not description:
                    error_count += 1
                    error_messages.append(f"행 {idx+1}: 지출 내역이 비어있습니다.")
                    continue
                
                # 금액 처리
                amount_value = row['금액']
                if isinstance(amount_value, str):
                    amount_value = amount_value.replace(',', '').replace('원', '').strip()
                    amount = float(amount_value)
                else:
                    amount = float(amount_value)
                
                if amount <= 0:
                    error_count += 1
                    error_messages.append(f"행 {idx+1}: 금액이 0 이하입니다.")
                    continue
                
                # 선택 필드
                category = str(row['카테고리']).strip() if pd.notna(row['카테고리']) else None
                merchant = str(row['지출처']).strip() if pd.notna(row['지출처']) else None
                
                # 카테고리가 없으면 자동 분류
                if not category:
                    category = category_classifier.classify(description)
                
                # DB 업데이트
                success = db_manager.update_expense(
                    expense_id=expense_id,
                    date=expense_date,
                    category=category,
                    description=description,
                    amount=amount,
                    merchant=merchant if merchant else None
                )
                
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    error_messages.append(f"행 {idx+1}: 지출(ID: {expense_id})을 찾을 수 없습니다.")
            
            except Exception as e:
                error_count += 1
                error_messages.append(f"행 {idx+1}: {str(e)}")
        
        # 결과 메시지 생성
        result_parts = []
        if delete_count > 0:
            result_parts.append(f"✅ {delete_count}건 삭제 완료")
        if success_count > 0:
            result_parts.append(f"✅ {success_count}건 수정 완료")
        if error_count > 0:
            result_parts.append(f"❌ {error_count}건 실패")
            if error_messages:
                result_parts.append("\n오류 상세:\n" + "\n".join(error_messages[:5]))
        
        if result_parts:
            result = "\n".join(result_parts)
        else:
            result = "변경사항이 없습니다."
        
        updated_table = get_expenses_table()
        return result, updated_table
        
    except Exception as e:
        error_msg = f"저장 중 오류 발생: {str(e)}"
        return error_msg, get_expenses_table()


def update_expense(
    expense_id: int,
    expense_date: str,
    category: str,
    description: str,
    amount: float,
    merchant: str
) -> Tuple[str, pd.DataFrame]:
    """
    지출 수정 비즈니스 로직
    
    Returns:
        (결과 메시지, 업데이트된 표)
    """
    try:
        global db_manager, category_classifier
        
        # Agent 초기화 확인
        if db_manager is None or category_classifier is None:
            initialize_agents()
        
        if not expense_id or expense_id <= 0:
            return "유효한 ID를 입력해주세요.", get_expenses_table()
        
        if not expense_date:
            return "날짜를 입력해주세요.", get_expenses_table()
        
        if not description or not description.strip():
            return "지출 내역을 입력해주세요.", get_expenses_table()
        
        if not amount or amount <= 0:
            return "올바른 금액을 입력해주세요.", get_expenses_table()
        
        # 날짜 형식 확인
        try:
            date_obj = parse_date(expense_date)
        except (ValueError, TypeError) as e:
            return f"날짜 형식이 올바르지 않습니다: {str(e)}", get_expenses_table()
        
        # 카테고리가 없으면 자동 분류
        final_category = category.strip() if category and category.strip() else None
        if not final_category:
            final_category = category_classifier.classify(description)
        
        final_merchant = merchant.strip() if merchant and merchant.strip() else None
        
        # DB 업데이트
        success = db_manager.update_expense(
            expense_id=expense_id,
            date=date_obj,
            category=final_category,
            description=description,
            amount=amount,
            merchant=final_merchant
        )
        
        if success:
            return f"지출(ID: {expense_id})이 성공적으로 수정되었습니다.", get_expenses_table()
        else:
            return f"지출(ID: {expense_id})을 찾을 수 없습니다.", get_expenses_table()
    except Exception as e:
        return f"오류 발생: {str(e)}", get_expenses_table()


def delete_expense(expense_id: int) -> Tuple[str, pd.DataFrame]:
    """
    지출 삭제 비즈니스 로직
    
    Returns:
        (결과 메시지, 업데이트된 표)
    """
    try:
        global db_manager
        
        # Agent 초기화 확인
        if db_manager is None:
            initialize_agents()
        
        if not expense_id or expense_id <= 0:
            return "유효한 ID를 입력해주세요.", get_expenses_table()
        
        # DB 삭제
        success = db_manager.delete_expense(expense_id)
        
        if success:
            return f"지출(ID: {expense_id})이 성공적으로 삭제되었습니다.", get_expenses_table()
        else:
            return f"지출(ID: {expense_id})을 찾을 수 없습니다.", get_expenses_table()
    except Exception as e:
        return f"오류 발생: {str(e)}", get_expenses_table()


def load_expense(expense_id: int) -> Tuple[str, str, str, str, float, str]:
    """
    수정을 위해 지출 데이터 로드
    
    Returns:
        (날짜, 카테고리, 설명, 금액, 지출처, 결과 메시지)
    """
    try:
        global db_manager
        
        # Agent 초기화 확인
        if db_manager is None:
            initialize_agents()
        
        if not expense_id or expense_id <= 0:
            return "", "", "", "", 0.0, "유효한 ID를 입력해주세요."
        
        expense = db_manager.get_expense_by_id(expense_id)
        if expense is None:
            return "", "", "", "", 0.0, f"지출(ID: {expense_id})을 찾을 수 없습니다."
        
        return (
            expense.date.isoformat() if expense.date else "",
            expense.category or "",
            expense.description or "",
            expense.amount or 0.0,
            expense.merchant or "",
            f"지출(ID: {expense_id}) 정보를 불러왔습니다."
        )
    except Exception as e:
        return "", "", "", "", 0.0, f"오류 발생: {str(e)}"


def get_category_chart(start_date: Optional[str] = None, end_date: Optional[str] = None) -> go.Figure:
    """카테고리별 지출 차트 생성"""
    try:
        global db_manager
        
        # Agent 초기화 확인
        if db_manager is None:
            initialize_agents()
        
        # 기간별 데이터 조회
        if start_date or end_date:
            start_date_obj = parse_date(start_date) if start_date else None
            end_date_obj = parse_date(end_date) if end_date else None
            expenses = db_manager.get_expenses(start_date=start_date_obj, end_date=end_date_obj)
        else:
            expenses = db_manager.get_all_expenses()
        if not expenses:
            fig = go.Figure()
            fig.add_annotation(
                text="데이터가 없습니다.",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False
            )
            return fig
        
        stats = calculate_category_stats(expenses)
        if not stats:
            fig = go.Figure()
            fig.add_annotation(
                text="데이터가 없습니다.",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False
            )
            return fig
        
        categories = list(stats.keys())
        totals = [stats[cat]['total'] for cat in categories]
        
        # 차트 제목에 기간 정보 추가
        title = "카테고리별 지출 총액"
        if start_date or end_date:
            period_str = f"{start_date if start_date else '전체'} ~ {end_date if end_date else '현재'}"
            title = f"카테고리별 지출 총액 ({period_str})"
        
        fig = go.Figure(data=[
            go.Bar(x=categories, y=totals, marker_color='steelblue')
        ])
        fig.update_layout(
            title=title,
            xaxis_title="카테고리",
            yaxis_title="금액 (원)",
            height=400
        )
        return fig
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(
            text=f"차트 생성 오류: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False
        )
        return fig


def get_category_pie_chart(start_date: Optional[str] = None, end_date: Optional[str] = None) -> go.Figure:
    """카테고리별 지출 파이 차트 생성"""
    try:
        global db_manager
        
        # Agent 초기화 확인
        if db_manager is None:
            initialize_agents()
        
        # 기간별 데이터 조회
        if start_date or end_date:
            start_date_obj = parse_date(start_date) if start_date else None
            end_date_obj = parse_date(end_date) if end_date else None
            expenses = db_manager.get_expenses(start_date=start_date_obj, end_date=end_date_obj)
        else:
            expenses = db_manager.get_all_expenses()
        if not expenses:
            fig = go.Figure()
            fig.add_annotation(
                text="데이터가 없습니다.",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False
            )
            return fig
        
        stats = calculate_category_stats(expenses)
        if not stats:
            fig = go.Figure()
            fig.add_annotation(
                text="데이터가 없습니다.",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False
            )
            return fig
        
        categories = list(stats.keys())
        totals = [stats[cat]['total'] for cat in categories]
        
        # 차트 제목에 기간 정보 추가
        title = "카테고리별 지출 비율"
        if start_date or end_date:
            period_str = f"{start_date if start_date else '전체'} ~ {end_date if end_date else '현재'}"
            title = f"카테고리별 지출 비율 ({period_str})"
        
        fig = go.Figure(data=[
            go.Pie(labels=categories, values=totals, hole=0.3)
        ])
        fig.update_layout(
            title=title,
            height=400
        )
        return fig
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(
            text=f"차트 생성 오류: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False
        )
        return fig


def get_analysis_dashboard(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Tuple[str, str, str, go.Figure, go.Figure]:
    """
    분석 대시보드 데이터 생성
    
    Args:
        start_date: 시작 날짜 (YYYY-MM-DD 형식, 선택사항)
        end_date: 종료 날짜 (YYYY-MM-DD 형식, 선택사항)
    
    Returns:
        (카테고리 통계, MoM 분석, 이상치 정보, 바 차트, 파이 차트)
    """
    try:
        global db_manager
        
        # Agent 초기화 확인
        if db_manager is None:
            initialize_agents()
        
        # 기간별 데이터 조회
        if start_date or end_date:
            start_date_obj = parse_date(start_date) if start_date else None
            end_date_obj = parse_date(end_date) if end_date else None
            expenses = db_manager.get_expenses(start_date=start_date_obj, end_date=end_date_obj)
        else:
            expenses = db_manager.get_all_expenses()
        
        if not expenses:
            empty_msg = "분석할 데이터가 없습니다."
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text="데이터가 없습니다.",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False
            )
            return empty_msg, empty_msg, empty_msg, empty_fig, empty_fig
        
        # 카테고리별 통계
        stats = calculate_category_stats(expenses)
        stats_text = "## 카테고리별 지출 통계\n\n"
        if stats:
            sorted_stats = sorted(stats.items(), key=lambda x: x[1]['total'], reverse=True)
            total_all = sum(s['total'] for s in stats.values())
            
            for category, stat in sorted_stats:
                percentage = (stat['total'] / total_all * 100) if total_all > 0 else 0
                stats_text += f"**{category}**: {stat['total']:,.0f}원 ({percentage:.1f}%) - {stat['count']}건\n"
            stats_text += f"\n**전체 총액**: {total_all:,.0f}원"
        else:
            stats_text = "통계 데이터가 없습니다."
        
        # MoM 분석
        mom_data = calculate_mom_growth(expenses)
        mom_text = "## Month-on-Month 증감 분석\n\n"
        if mom_data:
            for category, growth in sorted(mom_data.items(), key=lambda x: abs(x[1]), reverse=True):
                if growth == float('inf'):
                    mom_text += f"**{category}**: 신규 발생\n"
                elif growth > 0:
                    mom_text += f"**{category}**: +{growth:.1f}% 증가 ⬆️\n"
                elif growth < 0:
                    mom_text += f"**{category}**: {growth:.1f}% 감소 ⬇️\n"
                else:
                    mom_text += f"**{category}**: 변화 없음\n"
        else:
            mom_text += "분석할 데이터가 부족합니다."
        
        # 이상치 분석
        outliers = detect_outliers(expenses)
        outliers_text = f"## 이상치 분석\n\n"
        outliers_text += f"평균+2SD를 초과하는 이상치: **{len(outliers)}건**\n\n"
        if outliers:
            outliers_text += "주요 이상치:\n"
            for outlier in outliers[:5]:
                outliers_text += f"- [{outlier['date']}] {outlier['category']}: {outlier['description']} - {outlier['amount']:,.0f}원\n"
        else:
            outliers_text += "이상치가 발견되지 않았습니다."
        
        # 예상 월 지출
        predictions = predict_monthly_expense(expenses)
        if predictions:
            total_predicted = sum(predictions.values())
            outliers_text += f"\n\n## 예상 월 지출\n\n"
            outliers_text += f"**전체 예상 지출**: {total_predicted:,.0f}원\n\n"
            sorted_pred = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
            for category, amount in sorted_pred:
                percentage = (amount / total_predicted * 100) if total_predicted > 0 else 0
                outliers_text += f"- {category}: {amount:,.0f}원 ({percentage:.1f}%)\n"
        
        # 차트 생성
        bar_chart = get_category_chart(start_date, end_date)
        pie_chart = get_category_pie_chart(start_date, end_date)
        
        # 기간 정보 추가
        period_info = ""
        if start_date or end_date:
            period_info = f"\n**분석 기간**: {start_date if start_date else '전체'} ~ {end_date if end_date else '현재'}\n\n"
            stats_text = period_info + stats_text
        
        return stats_text, mom_text, outliers_text, bar_chart, pie_chart
    except Exception as e:
        error_msg = f"분석 중 오류 발생: {str(e)}"
        empty_fig = go.Figure()
        empty_fig.add_annotation(
            text=error_msg,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False
        )
        return error_msg, error_msg, error_msg, empty_fig, empty_fig


def generate_report(
    start_date: Optional[str],
    end_date: Optional[str],
    name: Optional[str] = None
) -> str:
    """
    리포트 생성 비즈니스 로직
    
    Args:
        start_date: 시작 날짜 (YYYY-MM-DD 형식, 선택사항)
        end_date: 종료 날짜 (YYYY-MM-DD 형식, 선택사항)
        name: 사용자 이름 (선택사항)
        
    Returns:
        마크다운 형식의 리포트
    """
    try:
        global user_name, report_agent
        
        # Agent 초기화 확인
        if report_agent is None:
            initialize_agents()
        
        if name:
            user_name = name.strip()
        
        report = report_agent.generate_report(
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            user_name=user_name if user_name else None
        )
        return report
    except Exception as e:
        return f"리포트 생성 중 오류 발생: {str(e)}"


def main():
    """메인 함수"""
    # Windows에서 이벤트 루프 정책 재설정 (안전장치)
    if sys.platform == 'win32':
        try:
            # 기존 루프가 있으면 닫기
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    loop.close()
            except RuntimeError:
                pass
            
            # WindowsSelectorEventLoopPolicy 설정
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception as e:
            print(f"이벤트 루프 정책 설정 경고: {e}")
    
    # Agent 초기화
    initialize_agents()
    
    # UI 생성 및 실행
    from ui_gradio import create_ui
    app = create_ui()
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    # Windows에서 이벤트 루프 정책을 메인 진입점에서 설정
    if sys.platform == 'win32':
        try:
            # 기존 루프가 있으면 정리
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    loop.close()
            except RuntimeError:
                pass
            
            # WindowsSelectorEventLoopPolicy 설정
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
            # 새 이벤트 루프 생성
            asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception as e:
            print(f"이벤트 루프 설정 경고: {e}")
    
    main()
