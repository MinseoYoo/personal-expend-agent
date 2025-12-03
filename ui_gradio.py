"""
Gradio 기반 지출 분석 서비스 UI 모듈
순수 프론트엔드 레이어 - UI 구성만 담당
"""

import gradio as gr
from datetime import date
from gradio_calendar import Calendar

# main 모듈의 비즈니스 로직 함수들을 직접 import하여 사용
from main import (
    add_expense,
    upload_csv,
    get_expenses_table,
    save_table_changes,
    get_analysis_dashboard,
    generate_report
)


def create_ui():
    """Gradio UI 생성"""
    # Windows 호환성을 위해 queue 비활성화 옵션 사용
    with gr.Blocks(title="지출 분석 서비스") as app:
        gr.Markdown("# 💰 지출 분석 서비스")
        gr.Markdown("LangChain Multi-Agent를 활용한 지출 관리 및 분석 시스템")
        
        with gr.Tabs():
            # 탭 1: 지출 입력
            with gr.Tab("📝 지출 입력"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 새로운 지출 추가")
                        
                        expense_date = Calendar(label="날짜", value=date.today().isoformat())
                        
                        with gr.Row():
                            category = gr.Textbox(
                                label="카테고리 (선택사항)",
                                placeholder="비어있으면 자동 분류됩니다",
                                value="",
                                scale=1
                            )
                            merchant = gr.Textbox(
                                label="지출처 (선택사항)",
                                placeholder="예: 스타벅스, 이마트 등",
                                value="",
                                scale=1
                            )
                        
                        description = gr.Textbox(
                            label="지출 내역",
                            placeholder="예: 점심 식사, 지하철 요금 등"
                        )
                        
                        amount = gr.Number(
                            label="금액 (원)",
                            value=0.0,
                            minimum=0
                        )
                        
                        submit_btn = gr.Button("추가", variant="primary")
                        result_msg = gr.Textbox(label="결과", interactive=False)
                        
                        submit_btn.click(
                            fn=add_expense,
                            inputs=[expense_date, category, description, amount, merchant],
                            outputs=[result_msg, expense_date, category, description, amount, merchant]
                        )
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### CSV 파일로 일괄 추가")
                        gr.Markdown("""
**CSV 파일 형식:**
- 필수 컬럼: `date`, `description`, `amount`
- 선택 컬럼: `category`, `merchant`

**예시:**
```csv
date,description,amount,category,merchant
2024-01-15,점심 식사,15000,식비,맛있는 식당
2024-01-16,지하철 요금,1400,교통비,
2024-01-17,커피,5000,,스타벅스
```
                        """)
                        
                        csv_upload = gr.File(
                            label="CSV 파일 선택",
                            file_types=[".csv"],
                            type="filepath"
                        )
                        
                        csv_upload_btn = gr.Button("CSV 파일 업로드", variant="primary")
                        csv_result_msg = gr.Textbox(label="업로드 결과", interactive=False, lines=10)
                
                # 지출 내역 표 및 수정/삭제
                gr.Markdown("---")
                gr.Markdown("### 📋 지출 내역 관리")
                
                refresh_table_btn = gr.Button("🔄 목록 새로고침", variant="secondary")
                expenses_table = gr.Dataframe(
                    label="지출 내역 (표에서 직접 수정 및 삭제 가능 - 삭제 컬럼에 체크 표시)",
                    headers=["ID", "날짜", "카테고리", "지출 내역", "금액", "지출처", "삭제"],
                    interactive=True,
                    wrap=True,
                    type="pandas"
                )
                gr.Markdown("💡 **사용법**: 표에서 직접 수정하거나, '삭제' 컬럼에 체크(True)를 표시한 후 '변경사항 저장' 버튼을 클릭하세요.")
                
                save_table_btn = gr.Button("💾 변경사항 저장", variant="primary")
                table_save_result = gr.Textbox(label="저장 결과", interactive=False)
                
                csv_upload_btn.click(
                    fn=upload_csv,
                    inputs=[csv_upload],
                    outputs=[csv_result_msg, expenses_table]
                )
                
                refresh_table_btn.click(
                    fn=get_expenses_table,
                    inputs=[],
                    outputs=[expenses_table]
                )
                
                save_table_btn.click(
                    fn=save_table_changes,
                    inputs=[expenses_table],
                    outputs=[table_save_result, expenses_table]
                )
                
                # 초기 로드
                app.load(
                    fn=get_expenses_table,
                    inputs=[],
                    outputs=[expenses_table],
                    api_name="load_expenses_table"
                )
                
            
            # 탭 2: 분석 대시보드
            with gr.Tab("📊 분석 대시보드"):
                gr.Markdown("### 지출 분석")
                
                with gr.Row():
                    analysis_start_date = Calendar(label="시작 날짜", value=date.today().isoformat())
                    analysis_end_date = Calendar(label="종료 날짜", value=date.today().isoformat())
                    refresh_btn = gr.Button("🔄 분석 새로고침", variant="primary", scale=1)
                
                gr.Markdown("💡 **기간을 지정하지 않으면 전체 기간을 분석합니다.**")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        stats_output = gr.Markdown(label="카테고리별 통계")
                    with gr.Column(scale=1):
                        mom_output = gr.Markdown(label="MoM 분석")
                
                outliers_output = gr.Markdown(label="이상치 및 예상 지출")
                
                with gr.Row():
                    bar_chart = gr.Plot(label="카테고리별 지출 (바 차트)")
                    pie_chart = gr.Plot(label="카테고리별 지출 비율 (파이 차트)")
                
                refresh_btn.click(
                    fn=get_analysis_dashboard,
                    inputs=[analysis_start_date, analysis_end_date],
                    outputs=[stats_output, mom_output, outliers_output, bar_chart, pie_chart],
                    api_name="refresh_analysis"
                )
                
                # 초기 로드
                app.load(
                    fn=get_analysis_dashboard,
                    inputs=[analysis_start_date, analysis_end_date],
                    outputs=[stats_output, mom_output, outliers_output, bar_chart, pie_chart],
                    api_name="load_analysis"
                )
            
            # 탭 3: 리포트
            with gr.Tab("📄 리포트 생성"):
                gr.Markdown("### 지출 분석 리포트 생성")
                
                user_name_input = gr.Textbox(
                    label="사용자 이름 (선택사항)",
                    placeholder="예: 홍길동",
                    value=""
                )
                
                with gr.Row():
                    report_start_date = Calendar(label="시작 날짜", value=date.today().isoformat())
                    report_end_date = Calendar(label="종료 날짜", value=date.today().isoformat())
                
                generate_btn = gr.Button("리포트 생성", variant="primary")
                report_output = gr.Markdown(label="리포트")
                
                generate_btn.click(
                    fn=generate_report,
                    inputs=[report_start_date, report_end_date, user_name_input],
                    outputs=[report_output],
                    show_progress=True
                )
        
        return app
