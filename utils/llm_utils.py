"""
LLM 유틸리티 모듈
"""

import os
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()


class CategoryClassifier:
    """카테고리 자동 분류 클래스"""
    
    # 일반적인 카테고리 목록
    DEFAULT_CATEGORIES = [
        "식비", "교통비", "쇼핑", "의료", "교육", "통신비", 
        "주거비", "문화/여가", "보험", "기타"
    ]
    
    def __init__(self, model_name: str = "gpt-3.5-turbo", temperature: float = 0.3):
        """
        초기화
        
        Args:
            model_name: 사용할 OpenAI 모델명
            temperature: 모델 온도 설정
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=temperature,
            api_key=api_key
        )
        
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", """당신은 지출 내역을 분석하여 적절한 카테고리로 분류하는 전문가입니다.
다음 카테고리 중 하나를 선택하여 반환하세요: {categories}

규칙:
1. 지출 내역의 내용을 분석하여 가장 적절한 카테고리를 선택하세요.
2. 카테고리명만 반환하세요 (설명 없이).
3. 명확하지 않은 경우 "기타"를 선택하세요.
4. 반드시 제공된 카테고리 목록 중 하나만 반환하세요."""),
            ("human", "지출 내역: {description}")
        ])
    
    def classify(self, description: str, categories: Optional[list] = None) -> str:
        """
        지출 내역을 카테고리로 분류
        
        Args:
            description: 지출 내역 텍스트
            categories: 사용 가능한 카테고리 목록 (None이면 기본 카테고리 사용)
            
        Returns:
            분류된 카테고리명
        """
        if not description or not description.strip():
            return "기타"
        
        if categories is None:
            categories = self.DEFAULT_CATEGORIES
        
        categories_str = ", ".join(categories)
        
        try:
            prompt = self.prompt_template.format_messages(
                categories=categories_str,
                description=description.strip()
            )
            response = self.llm.invoke(prompt)
            category = response.content.strip()
            
            # 응답이 카테고리 목록에 있는지 확인
            if category in categories:
                return category
            else:
                # 응답에서 카테고리명 추출 시도
                for cat in categories:
                    if cat in category:
                        return cat
                return "기타"
        except Exception as e:
            print(f"카테고리 분류 중 오류 발생: {e}")
            return "기타"

