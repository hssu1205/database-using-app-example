import streamlit as st
from streamlit_drawable_canvas import st_canvas
import firebase_admin
from firebase_admin import credentials, firestore, storage
from datetime import datetime
from PIL import Image
import io
import json
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Firebase 초기화
if not firebase_admin._apps:
    # secrets.toml에서 Firebase 설정 읽기
    firebase_config = {
        "type": st.secrets["firebase"]["type"],
        "project_id": st.secrets["firebase"]["project_id"],
        "private_key_id": st.secrets["firebase"]["private_key_id"],
        "private_key": st.secrets["firebase"]["private_key"],
        "client_email": st.secrets["firebase"]["client_email"],
        "client_id": st.secrets["firebase"]["client_id"],
        "auth_uri": st.secrets["firebase"]["auth_uri"],
        "token_uri": st.secrets["firebase"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"],
        "universe_domain": st.secrets["firebase"]["universe_domain"]
    }
    
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred, {
        'storageBucket': st.secrets["firebase"]["storage_bucket"]
    })

# Firestore 클라이언트
db = firestore.client()

# 페이지 설정
st.set_page_config(page_title="학생 정서 모니터링", page_icon="😊", layout="wide")

# Session state 초기화
if 'mode' not in st.session_state:
    st.session_state.mode = 'student'
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# 사이드바에 모드 선택
with st.sidebar:
    st.title("🔐 모드 선택")
    mode_option = st.radio(
        "모드를 선택하세요:",
        ["👨‍🎓 학생 모드", "👨‍🏫 교사 모드"],
        index=0 if st.session_state.mode == 'student' else 1
    )
    
    if mode_option == "👨‍🎓 학생 모드":
        st.session_state.mode = 'student'
        st.session_state.authenticated = False
    else:
        st.session_state.mode = 'teacher'

# 교사 모드 - 비밀번호 인증
if st.session_state.mode == 'teacher' and not st.session_state.authenticated:
    st.title("👨‍🏫 교사 모드")
    st.write("교사 모드에 접속하려면 비밀번호를 입력하세요.")
    
    password = st.text_input("비밀번호", type="password", key="teacher_password")
    
    if st.button("로그인", type="primary"):
        if password == "teacher":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ 비밀번호가 올바르지 않습니다.")
    
    st.stop()

# 교사 모드 - 대시보드
if st.session_state.mode == 'teacher' and st.session_state.authenticated:
    st.title("👨‍🏫 교사 대시보드")
    st.write("학생들의 정서 데이터와 그림을 확인하세요.")
    
    # 로그아웃 버튼
    with st.sidebar:
        if st.button("🚪 로그아웃", type="secondary"):
            st.session_state.authenticated = False
            st.rerun()
    
    try:
        # Firestore에서 데이터 가져오기
        emotions_ref = db.collection('student_emotions')
        docs = emotions_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        
        emotions_data = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            emotions_data.append(data)
        
        if not emotions_data:
            st.info("📭 아직 제출된 데이터가 없습니다.")
        else:
            st.success(f"📊 총 {len(emotions_data)}개의 기록이 있습니다.")
            
            # 두 컬럼으로 나누기
            col1, col2 = st.columns([1, 1])
            
            # 왼쪽: 감정 데이터 시각화
            with col1:
                st.subheader("📊 감정 분포 차트")
                
                # 감정별 카운트
                emotion_counts = {}
                for data in emotions_data:
                    emotion_display = data.get('emotion_display', '알 수 없음')
                    emotion_counts[emotion_display] = emotion_counts.get(emotion_display, 0) + 1
                
                # DataFrame 생성
                df_emotions = pd.DataFrame(list(emotion_counts.items()), 
                                          columns=['감정', '학생 수'])
                df_emotions = df_emotions.sort_values('학생 수', ascending=False)
                
                # 막대 그래프
                fig = px.bar(df_emotions, 
                            x='감정', 
                            y='학생 수',
                            title='감정 상태별 학생 수',
                            color='학생 수',
                            color_continuous_scale='Viridis',
                            text='학생 수')
                
                fig.update_traces(texttemplate='%{text}명', textposition='outside')
                fig.update_layout(
                    xaxis_title="감정 상태",
                    yaxis_title="학생 수",
                    showlegend=False,
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 상세 데이터 테이블
                st.subheader("📋 상세 데이터")
                
                # 테이블용 데이터 준비
                table_data = []
                for data in emotions_data:
                    table_data.append({
                        '학생 이름': data.get('student_name', '알 수 없음'),
                        '감정': data.get('emotion_display', '알 수 없음'),
                        '제출 시간': data.get('timestamp').strftime('%Y-%m-%d %H:%M:%S') if data.get('timestamp') else '알 수 없음'
                    })
                
                df_table = pd.DataFrame(table_data)
                st.dataframe(df_table, use_container_width=True, height=300)
            
            # 오른쪽: 그림 갤러리
            with col2:
                st.subheader("🎨 학생 그림 갤러리")
                
                # 그림을 3열로 표시
                for i in range(0, len(emotions_data), 3):
                    cols = st.columns(3)
                    for j in range(3):
                        if i + j < len(emotions_data):
                            data = emotions_data[i + j]
                            with cols[j]:
                                try:
                                    # 이미지 URL로부터 이미지 표시
                                    image_url = data.get('image_url')
                                    if image_url:
                                        st.image(image_url, 
                                                caption=f"{data.get('student_name', '알 수 없음')}\n{data.get('emotion_display', '')}",
                                                use_container_width=True)
                                    else:
                                        st.warning("이미지 없음")
                                except Exception as e:
                                    st.error(f"이미지 로드 실패: {str(e)}")
    
    except Exception as e:
        st.error(f"❌ 데이터를 불러오는 중 오류가 발생했습니다: {str(e)}")
    
    st.stop()

# 학생 모드
st.title("😊 학생 정서 모니터링")
st.write("오늘의 감정을 표현해주세요!")

# 구분선
st.divider()

# 학생 이름 입력
st.subheader("📝 학생 정보")
student_name = st.text_input("이름을 입력하세요", placeholder="홍길동")

st.divider()

# 감정 상태 선택
st.subheader("💭 오늘의 감정")
emotion_options = {
    "😊 매우 좋아요": "very_happy",
    "🙂 좋아요": "happy",
    "😐 보통이에요": "neutral",
    "😔 슬퍼요": "sad",
    "😢 매우 슬퍼요": "very_sad",
    "😡 화나요": "angry",
    "😰 불안해요": "anxious"
}

selected_emotion = st.radio(
    "현재 기분을 선택해주세요:",
    options=list(emotion_options.keys()),
    index=0
)

st.divider()

# 그림 그리기 캔버스
st.subheader("🎨 감정을 그림으로 표현해주세요")
st.write("아래 캔버스에 현재 감정을 그림으로 그려주세요.")

# 캔버스 설정
canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 0)",
    stroke_width=3,
    stroke_color="#000000",
    background_color="#FFFFFF",
    height=400,
    width=600,
    drawing_mode="freedraw",
    key="canvas",
)

st.divider()

# 제출 버튼
if st.button("📤 제출하기", type="primary", use_container_width=True):
    if not student_name:
        st.error("⚠️ 이름을 입력해주세요!")
    elif canvas_result.image_data is None:
        st.error("⚠️ 그림을 그려주세요!")
    else:
        try:
            with st.spinner("데이터를 저장하는 중..."):
                # 현재 시간
                timestamp = datetime.now()
                
                # 이미지를 PIL Image로 변환
                image = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                # RGB로 변환 (JPG는 투명도를 지원하지 않음)
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[3])  # 알파 채널을 마스크로 사용
                
                # 이미지를 바이트로 변환
                img_byte_arr = io.BytesIO()
                rgb_image.save(img_byte_arr, format='JPEG', quality=95)
                img_byte_arr.seek(0)
                
                # Storage에 이미지 업로드
                bucket = storage.bucket()
                blob_name = f"drawings/{student_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                blob = bucket.blob(blob_name)
                blob.upload_from_file(img_byte_arr, content_type='image/jpeg')
                
                # 공개 URL 생성 (선택사항)
                blob.make_public()
                image_url = blob.public_url
                
                # Firestore에 데이터 저장
                doc_ref = db.collection('student_emotions').add({
                    'student_name': student_name,
                    'emotion': emotion_options[selected_emotion],
                    'emotion_display': selected_emotion,
                    'image_path': blob_name,
                    'image_url': image_url,
                    'timestamp': timestamp
                })
                
                st.success("✅ 감정 기록이 성공적으로 저장되었습니다!")
                st.balloons()
                
                # 저장된 정보 표시
                with st.expander("저장된 정보 보기"):
                    st.write(f"**이름:** {student_name}")
                    st.write(f"**감정:** {selected_emotion}")
                    st.write(f"**저장 시간:** {timestamp.strftime('%Y년 %m월 %d일 %H:%M:%S')}")
                    st.write(f"**이미지 경로:** {blob_name}")
                
        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {str(e)}")
            st.write("자세한 오류 정보:", e)

# 푸터
st.divider()
st.caption("💡 학생의 정서를 모니터링하고 관리하는 시스템입니다.")

