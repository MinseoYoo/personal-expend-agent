"""
DB 관리 Agent
"""

import os
from datetime import date
from typing import Optional, List
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import StructuredTool
from dotenv import load_dotenv

from database.db_manager import DatabaseManager
from database.models import Expense
from utils.llm_utils import CategoryClassifier

load_dotenv()


class DBAgent:
    """데이터베이스 관리 Agent"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        초기화
        
        Args:
            db_manager: DatabaseManager 인스턴스
        """
        self.db_manager = db_manager
        self.category_classifier = CategoryClassifier()
        
        # 도구 정의
        self.tools = self._create_tools()
        
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
            ("system", """당신은 지출 데이터를 관리하는 전문가입니다.
사용자의 요청에 따라 지출 데이터를 추가하거나 조회할 수 있습니다.
카테고리가 제공되지 않으면 자동으로 분류해야 합니다."""),
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
    
    def _create_tools(self) -> List[StructuredTool]:
        """도구 생성"""
        
        def add_expense(
            date_str: str,
            description: str,
            amount: float,
            category: Optional[str] = None,
            merchant: Optional[str] = None
        ) -> str:
            """
            지출을 데이터베이스에 추가합니다.
            
            Args:
                date_str: 날짜 (YYYY-MM-DD 형식)
                description: 지출 내역
                amount: 금액
                category: 카테고리 (선택사항, 없으면 자동 분류)
                merchant: 지출처 (선택사항)
                
            Returns:
                추가 결과 메시지
            """
            try:
                expense_date = date.fromisoformat(date_str)
                
                # 카테고리가 없으면 자동 분류
                if not category or category.strip() == "":
                    category = self.category_classifier.classify(description)
                
                expense_id = self.db_manager.add_expense(
                    date=expense_date,
                    category=category,
                    description=description,
                    amount=amount,
                    merchant=merchant
                )
                
                return f"지출이 성공적으로 추가되었습니다. ID: {expense_id}, 카테고리: {category}"
            except Exception as e:
                return f"오류 발생: {str(e)}"
        
        def get_expenses(
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
        ) -> str:
            """
            기간별 지출을 조회합니다.
            
            Args:
                start_date: 시작 날짜 (YYYY-MM-DD 형식, 선택사항)
                end_date: 종료 날짜 (YYYY-MM-DD 형식, 선택사항)
                
            Returns:
                지출 목록 문자열
            """
            try:
                start = date.fromisoformat(start_date) if start_date else None
                end = date.fromisoformat(end_date) if end_date else None
                
                expenses = self.db_manager.get_expenses(start_date=start, end_date=end)
                
                if not expenses:
                    return "조회된 지출이 없습니다."
                
                result = f"총 {len(expenses)}개의 지출이 조회되었습니다:\n\n"
                for exp in expenses[:20]:  # 최대 20개만 표시
                    result += f"- [{exp.date}] {exp.category}: {exp.description} - {exp.amount:,.0f}원\n"
                
                if len(expenses) > 20:
                    result += f"\n... 외 {len(expenses) - 20}개 더"
                
                return result
            except Exception as e:
                return f"오류 발생: {str(e)}"
        
        def classify_category(description: str) -> str:
            """
            지출 내역을 분석하여 카테고리를 자동 분류합니다.
            
            Args:
                description: 지출 내역
                
            Returns:
                분류된 카테고리명
            """
            try:
                category = self.category_classifier.classify(description)
                return f"분류된 카테고리: {category}"
            except Exception as e:
                return f"오류 발생: {str(e)}"
        
        return [
            StructuredTool.from_function(
                func=add_expense,
                name="add_expense",
                description="지출을 데이터베이스에 추가합니다. 날짜는 YYYY-MM-DD 형식으로 입력하세요."
            ),
            StructuredTool.from_function(
                func=get_expenses,
                name="get_expenses",
                description="기간별 지출을 조회합니다. 날짜는 YYYY-MM-DD 형식으로 입력하세요."
            ),
            StructuredTool.from_function(
                func=classify_category,
                name="classify_category",
                description="지출 내역을 분석하여 카테고리를 자동 분류합니다."
            ),
        ]
    
    def run(self, query: str) -> str:
        """
        Agent 실행
        
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

