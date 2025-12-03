"""
지출 분석 Agent
"""

import os
import json
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import StructuredTool
from dotenv import load_dotenv

from database.db_manager import DatabaseManager
from utils.analysis_utils import (
    calculate_category_stats,
    calculate_mom_growth,
    detect_outliers,
    predict_monthly_expense,
    parse_date
)

load_dotenv()


class AnalysisAgent:
    """지출 분석 Agent"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        초기화
        
        Args:
            db_manager: DatabaseManager 인스턴스
        """
        self.db_manager = db_manager
        
        # 도구 정의
        self.tools, self.tool_functions = self._create_tools()
        
        # LLM 초기화
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.3,
            api_key=api_key
        )
        
        # Agent 프롬프트
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 지출 데이터를 분석하는 전문가입니다.
사용자의 요청에 따라 다양한 통계 분석을 수행하고 인사이트를 제공할 수 있습니다.
분석 결과를 명확하고 이해하기 쉽게 설명하세요."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Agent 생성
        agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )
    
    def _create_tools(self) -> Tuple[List[StructuredTool], Dict]:
        """도구 생성
        
        Returns:
            (도구 리스트, 도구 함수 딕셔너리)
        """
        
        def get_category_statistics(
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
        ) -> str:
            """
            카테고리별 지출 통계를 계산합니다.
            
            Args:
                start_date: 시작 날짜 (YYYY-MM-DD 형식, 선택사항)
                end_date: 종료 날짜 (YYYY-MM-DD 형식, 선택사항)
                
            Returns:
                카테고리별 통계 문자열
            """
            try:
                start = parse_date(start_date) if start_date else None
                end = parse_date(end_date) if end_date else None
                
                expenses = self.db_manager.get_expenses(start_date=start, end_date=end)
                stats = calculate_category_stats(expenses)
                
                if not stats:
                    return "분석할 데이터가 없습니다."
                
                result = "카테고리별 지출 통계:\n\n"
                # 총액 기준으로 정렬
                sorted_stats = sorted(stats.items(), key=lambda x: x[1]['total'], reverse=True)
                
                total_all = sum(s['total'] for s in stats.values())
                
                for category, stat in sorted_stats:
                    percentage = (stat['total'] / total_all * 100) if total_all > 0 else 0
                    result += f"【{category}】\n"
                    result += f"  총액: {stat['total']:,.0f}원 ({percentage:.1f}%)\n"
                    result += f"  건수: {stat['count']}건\n"
                    result += f"  평균: {stat['mean']:,.0f}원\n"
                    result += f"  최소: {stat['min']:,.0f}원 / 최대: {stat['max']:,.0f}원\n\n"
                
                result += f"전체 총액: {total_all:,.0f}원"
                return result
            except Exception as e:
                return f"오류 발생: {str(e)}"
        
        def calculate_mom_growth_analysis(
            current_month: Optional[str] = None
        ) -> str:
            """
            Month-on-Month 증감률을 계산합니다.
            
            Args:
                current_month: 현재 월 (YYYY-MM 형식, 선택사항)
                
            Returns:
                MoM 증감률 분석 문자열
            """
            try:
                if current_month:
                    year, month = map(int, current_month.split('-'))
                    target_date = date(year, month, 15)
                else:
                    target_date = date.today()
                
                # 충분한 데이터를 가져오기 위해 3개월치 데이터 조회
                start_date = target_date - timedelta(days=90)
                expenses = self.db_manager.get_expenses(start_date=start_date)
                
                mom_data = calculate_mom_growth(expenses, target_date)
                
                if not mom_data:
                    return "분석할 데이터가 부족합니다."
                
                result = f"{target_date.year}년 {target_date.month}월 대비 전월 증감률:\n\n"
                
                for category, growth in sorted(mom_data.items(), key=lambda x: abs(x[1]), reverse=True):
                    if growth == float('inf'):
                        result += f"【{category}】: 신규 발생 (+∞%)\n"
                    elif growth > 0:
                        result += f"【{category}】: +{growth:.1f}% 증가\n"
                    elif growth < 0:
                        result += f"【{category}】: {growth:.1f}% 감소\n"
                    else:
                        result += f"【{category}】: 변화 없음\n"
                
                return result
            except Exception as e:
                return f"오류 발생: {str(e)}"
        
        def detect_outliers_analysis(
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
        ) -> str:
            """
            평균+2SD 이상의 이상치를 탐지합니다.
            
            Args:
                start_date: 시작 날짜 (YYYY-MM-DD 형식, 선택사항)
                end_date: 종료 날짜 (YYYY-MM-DD 형식, 선택사항)
                
            Returns:
                이상치 분석 문자열
            """
            try:
                start = parse_date(start_date) if start_date else None
                end = parse_date(end_date) if end_date else None
                
                expenses = self.db_manager.get_expenses(start_date=start, end_date=end)
                outliers = detect_outliers(expenses)
                
                if not outliers:
                    return "이상치가 발견되지 않았습니다."
                
                result = f"이상치 {len(outliers)}건 발견 (평균+2SD 초과):\n\n"
                
                for outlier in outliers[:10]:  # 최대 10개만 표시
                    result += f"• [{outlier['date']}] {outlier['category']}: {outlier['description']}\n"
                    result += f"  금액: {outlier['amount']:,.0f}원 (임계값: {outlier['threshold']:,.0f}원)\n"
                    result += f"  평균: {outlier['mean']:,.0f}원, 표준편차: {outlier['std']:,.0f}원\n\n"
                
                if len(outliers) > 10:
                    result += f"... 외 {len(outliers) - 10}건 더"
                
                return result
            except Exception as e:
                return f"오류 발생: {str(e)}"
        
        def predict_monthly_expense_analysis(
            target_month: Optional[str] = None
        ) -> str:
            """
            회귀 분석을 사용하여 월 지출을 예상합니다.
            
            Args:
                target_month: 예측할 월 (YYYY-MM 형식, 선택사항)
                
            Returns:
                월 지출 예상 문자열
            """
            try:
                if target_month:
                    year, month = map(int, target_month.split('-'))
                    target_date = date(year, month, 15)
                else:
                    target_date = date.today()
                
                # 충분한 데이터를 가져오기 위해 6개월치 데이터 조회
                start_date = target_date - timedelta(days=180)
                expenses = self.db_manager.get_expenses(start_date=start_date)
                
                predictions = predict_monthly_expense(expenses, target_date)
                
                if not predictions:
                    return "예측할 데이터가 부족합니다."
                
                total_predicted = sum(predictions.values())
                
                result = f"{target_date.year}년 {target_date.month}월 예상 지출:\n\n"
                
                # 예상 금액 기준으로 정렬
                sorted_predictions = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
                
                for category, amount in sorted_predictions:
                    percentage = (amount / total_predicted * 100) if total_predicted > 0 else 0
                    result += f"【{category}】: {amount:,.0f}원 ({percentage:.1f}%)\n"
                
                result += f"\n전체 예상 지출: {total_predicted:,.0f}원"
                return result
            except Exception as e:
                return f"오류 발생: {str(e)}"
        
        tools = [
            StructuredTool.from_function(
                func=get_category_statistics,
                name="get_category_statistics",
                description="카테고리별 지출 통계를 계산합니다. 날짜는 YYYY-MM-DD 형식으로 입력하세요."
            ),
            StructuredTool.from_function(
                func=calculate_mom_growth_analysis,
                name="calculate_mom_growth",
                description="Month-on-Month 증감률을 계산합니다. 월은 YYYY-MM 형식으로 입력하세요."
            ),
            StructuredTool.from_function(
                func=detect_outliers_analysis,
                name="detect_outliers",
                description="평균+2SD 이상의 이상치를 탐지합니다. 날짜는 YYYY-MM-DD 형식으로 입력하세요."
            ),
            StructuredTool.from_function(
                func=predict_monthly_expense_analysis,
                name="predict_monthly_expense",
                description="회귀 분석을 사용하여 월 지출을 예상합니다. 월은 YYYY-MM 형식으로 입력하세요."
            ),
        ]
        
        # 도구 함수들을 딕셔너리로 저장 (직접 호출용)
        tool_functions = {
            'get_category_statistics': get_category_statistics,
            'calculate_mom_growth': calculate_mom_growth_analysis,
            'detect_outliers': detect_outliers_analysis,
            'predict_monthly_expense': predict_monthly_expense_analysis,
        }
        
        return tools, tool_functions
    
    def get_all_analysis(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        LLM 없이 모든 분석을 직접 수행하고 결과를 반환
        
        Args:
            start_date: 시작 날짜 (YYYY-MM-DD 형식, 선택사항)
            end_date: 종료 날짜 (YYYY-MM-DD 형식, 선택사항)
            
        Returns:
            모든 분석 결과를 합친 문자열
        """
        results = []
        
        try:
            # 1. 카테고리별 통계
            category_stats = self.tool_functions['get_category_statistics'](
                start_date=start_date,
                end_date=end_date
            )
            results.append(category_stats)
            
            # 2. MoM 분석 (날짜 파싱하여 월 추출)
            if end_date:
                # end_date에서 YYYY-MM 추출
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                    current_month = date_obj.strftime("%Y-%m")
                except:
                    current_month = None
            else:
                current_month = None
            
            mom_analysis = self.tool_functions['calculate_mom_growth'](
                current_month=current_month
            )
            results.append(mom_analysis)
            
            # 3. 이상치 탐지
            outliers_analysis = self.tool_functions['detect_outliers'](
                start_date=start_date,
                end_date=end_date
            )
            results.append(outliers_analysis)
            
            # 4. 예상 지출 (날짜 파싱하여 월 추출)
            if end_date:
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                    target_month = date_obj.strftime("%Y-%m")
                except:
                    target_month = None
            else:
                target_month = None
            
            prediction_analysis = self.tool_functions['predict_monthly_expense'](
                target_month=target_month
            )
            results.append(prediction_analysis)
            
            return "\n\n".join(results)
        except Exception as e:
            return f"분석 중 오류 발생: {str(e)}"
    
    def run(self, query: str) -> str:
        """
        Agent 실행 (LLM 사용 - 하위 호환성을 위해 유지)
        
        Args:
            query: 사용자 쿼리
            
        Returns:
            Agent 응답
        """
        try:
            result = self.agent_executor.invoke({"input": query, "chat_history": []})
            return result.get("output", "처리 완료")
        except Exception as e:
            return f"오류 발생: {str(e)}"

