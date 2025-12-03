"""
리포트 생성 Agent
"""

import os
from typing import Optional
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from database.db_manager import DatabaseManager
from utils.analysis_utils import parse_date

load_dotenv()


class ReportAgent:
    """리포트 생성 Agent"""
    
    def __init__(self, db_manager: DatabaseManager, analysis_agent: 'AnalysisAgent'):
        """
        초기화
        
        Args:
            db_manager: DatabaseManager 인스턴스
            analysis_agent: AnalysisAgent 인스턴스
        """
        self.db_manager = db_manager
        self.analysis_agent = analysis_agent
        
        # LLM 초기화 (Chat Completion 사용)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.4,
            api_key=api_key
        )
        
        # 시스템 프롬프트
        self.system_prompt = """역할(Role)
당신은 사용자의 개인 지출 데이터를 분석해주는 전문가입니다. 

## 목표(Goal)
사용자가 제공한 한 달 지출 데이터를 소비 패턴, 주의해야 할 지출, 개선 포인트, 실천 가능한 조언을 중심으로 분석해서 리포트를 생성하세요.

## 톤(Tone)
- 판단적 표현을 지양하세요 (“너무 많이 썼다” 대신 “이번 달은 ○○에 비중이 많이 갔네!”)
- 부담 없는 친구처럼 편안하지만, 내용은 실제로 도움이 되는 재무 코치처럼 실질적 내용을 담아 작성해주세요.
- "-해요" 체를 사용하세요.

## 출력 포맷(Output Format)
이번 달 지출의 핵심 인사이트 한 문장
전체 지출 개요 (눈에 띄는 변화나 특징)
카테고리별 지출 패턴, 비정기적 지출 등의 분석
좋았던 점 (긍정적이거나 잘 한 소비 습관)
아쉬운 점과 개선 팁, 바로 실천 가능한 2~3가지 행동"""
    
    
    def generate_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_name: Optional[str] = None
    ) -> str:
        """
        리포트 생성
        
        Args:
            start_date: 시작 날짜 (YYYY-MM-DD 형식, 선택사항)
            end_date: 종료 날짜 (YYYY-MM-DD 형식, 선택사항)
            user_name: 사용자 이름 (선택사항)
            
        Returns:
            마크다운 형식의 리포트
        """
        try:
            # 설정한 기간의 데이터를 변수에 저장
            start_date_obj = parse_date(start_date) if start_date else None
            end_date_obj = parse_date(end_date) if end_date else None
            
            # 기간별 지출 데이터 불러오기
            expenses = self.db_manager.get_expenses(
                start_date=start_date_obj,
                end_date=end_date_obj
            )
            
            if not expenses:
                return "# 📊 지출 분석 리포트\n\n분석할 데이터가 없습니다."
            
            
            # 리포트 생성
            report = "# 📊 지출 분석 리포트\n\n"
            if user_name:
                report += f"**{user_name}님의 지출 분석 리포트**\n\n"
            report += f"**분석 기간**: {start_date if start_date else '전체'} ~ {end_date if end_date else '현재'}\n\n"
            report += f"**총 지출 건수**: {len(expenses)}건\n\n"
            
            report += "---\n\n" 
            try:
                # 모든 분석을 직접 수행 (LLM 호출 없음)
                analysis_result = self.analysis_agent.get_all_analysis(
                    start_date=start_date,
                    end_date=end_date
                )
            except Exception as e:
                analysis_result = f"분석 중 오류 발생: {str(e)}"
            
            # 지출 데이터를 JSON 형식으로 준비
            expenses_data = [
                {
                    "date": str(exp.date),
                    "category": exp.category,
                    "description": exp.description,
                    "amount": float(exp.amount),
                    "merchant": exp.merchant
                }
                for exp in expenses
            ]
            
            # Chat Completion을 사용하여 소비 제안 생성
            user_message = f"""사용자의 지출 데이터: {expenses_data}
            사용자의 지출 데이터에 대한 통계분석: {analysis_result}"""
            
            try:
                # Chat Completion 직접 호출
                messages = [
                    ("system", self.system_prompt),
                    ("human", user_message)
                ]
                result = self.llm.invoke(messages)
                llm_response = result.content if hasattr(result, 'content') else str(result)
                # 기존 리포트 헤더에 LLM 응답 추가
                report += llm_response
                print(report)
            except Exception as e:
                report += f"*소비 제안 생성 중 오류가 발생했습니다: {str(e)}*\n"
            
            return report
        except Exception as e:
            return f"리포트 생성 중 오류 발생: {str(e)}"

