# Open AI의 Playground에서의 여러 시도를 통해 완성한 프롬프트와 STT & TTS를 연결하여 음성 챗봇을 테스트해본 코드입니다.
# 아직 백엔드 서버가 구축되지 않아 streamlit을 이용하였습니다.(시연 영상용)

import os
import streamlit as st
import io
import sounddevice as sd
import numpy as np
import pydub
import speech_recognition as sr
from google.cloud import speech
from google.cloud import texttospeech as tts
from openai import OpenAI

# OpenAI API 키 설정
client = OpenAI(api_key="발급받은 키")

# Google Cloud 서비스 계정 자격 증명 파일 설정
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "Google Clout API 키 파일 위치"

# 초기 메시지 설정
initial_message = "안녕하세요! 소담이에요. 오늘 하루는 어떻게 보냈는지 이야기해 주세요."

# TTS 함수: 텍스트를 음성으로 변환
def synthesize_speech(text):
    try:
        client = tts.TextToSpeechClient()
        synthesis_input = tts.SynthesisInput(text=text)
        voice = tts.VoiceSelectionParams(language_code="ko-KR", ssml_gender=tts.SsmlVoiceGender.FEMALE)
        audio_config = tts.AudioConfig(audio_encoding=tts.AudioEncoding.LINEAR16)
        response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        return response.audio_content
    except Exception as e:
        st.error(f"TTS 에러: {e}")
        return None

# 음성을 재생하는 함수
def play_audio(audio_data):
    if audio_data:
        audio_segment = pydub.AudioSegment.from_file(io.BytesIO(audio_data), format="wav")
        raw_data = np.frombuffer(audio_segment.raw_data, dtype=np.int16)
        sample_rate = audio_segment.frame_rate
        sd.play(raw_data, samplerate=sample_rate)
        sd.wait()

# 음성 입력을 위한 함수
def get_audio_input():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.write("말씀하세요...")
        audio = r.listen(source)
    try:
        # Google Speech-to-Text API 사용
        client = speech.SpeechClient()
        audio_data = audio.get_wav_data()
        audio = speech.RecognitionAudio(content=audio_data)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=44100,  # 샘플링 속도를 44100 Hz로 설정
            language_code="ko-KR"
        )
        response = client.recognize(config=config, audio=audio)
        user_input = response.results[0].alternatives[0].transcript
        return user_input
    except Exception as e:
        st.write(f"음성을 인식할 수 없습니다: {e}")
        return None

# 챗봇 응답을 얻는 함수
def get_chatbot_response(messages):
    try:
        # OpenAI API를 사용하여 GPT 모델로부터 응답 생성
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        # 생성된 텍스트 응답을 클라이언트에 반환
        generated_text = response.choices[0].message.content.strip()
        return generated_text
    except Exception as e:
        print(f"Error in /generate: {e}")
        return f"Error: {str(e)}"

# 일기 생성 함수
def generate_diary_entry(conversation):
    diary_text = "=== 오늘의 일기 ===\n"
    for speaker, text in conversation:
        if speaker == "사용자":
            diary_text += f"{text}\n"
    return diary_text

def main():
    st.title("음성 대화 챗봇")

    # Streamlit의 상태를 관리하기 위한 변수
    if 'initial_message_played' not in st.session_state:
        st.session_state.initial_message_played = False

    if 'conversation' not in st.session_state:
        st.session_state.conversation = []

    # 초기 메시지 출력 및 재생
    if not st.session_state.initial_message_played:
        st.session_state.conversation.append(("소담", initial_message))
        audio_response = synthesize_speech(initial_message)
        if audio_response:
            play_audio(audio_response)
        st.session_state.initial_message_played = True

    # 대화 내용 시각화 함수
    def display_conversation(conversation):
        for speaker, text in conversation:
            if speaker == "사용자":
                st.markdown(f"<div style='text-align: right; background-color: #DCF8C6; padding: 10px; border-radius: 10px; margin: 10px;'>{text}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align: left; background-color: #E2E2E2; padding: 10px; border-radius: 10px; margin: 10px;'>{text}</div>", unsafe_allow_html=True)

    display_conversation(st.session_state.conversation)

    # 사용자 음성 입력 받기
    if st.button("마이크 켜기"):
        user_input = get_audio_input()
        if user_input:
            st.session_state.conversation.append(("사용자", user_input))
            st.write(f"사용자: {user_input}")

            if user_input.lower() in ["그만", "종료", "끝"]:
                diary_entry = generate_diary_entry(st.session_state.conversation)
                st.write("\n=== 오늘의 일기 ===")
                st.write(diary_entry)
                return

            messages = [
                {"role": "system", "content": (
                    "<Your role>a helpful assistant that assists elderly users by regularly engaging them in conversations, "
                    "recording their daily activities, monitoring their health, and conveying important messages to their family members.</Your role>\n"
                    "<Requirements>You should ask questions below(<Necessary questions you must ask>) naturally so that the user can feel as if they are just chatting with you. "
                    "Let the user not feel the awkwardness(like filling out a format)when you ask the questions.</Requirements>\n"
                    "<Necessary questions you must ask>\n"
                    "1. questions that must be asked to write a diary\n"
                    "2. question about what the user wants to remember\n"
                    "3. questions that can check the user's today's physical and emotional conditions\n"
                    "4. Questions that ask the things the user wants to say to his or her child\n"
                    "5. questions that can check the user's memory precision about 'the things that I want to remember' which the user said yesterday\n"
                    "</Necessary questions you must ask>\n"
                    "<Output> You should complete a diary in Korean by summarizing the user's answers to the question you asked.</Output>"
                )}
            ]
            for speaker, text in st.session_state.conversation:
                role = "user" if speaker == "사용자" else "assistant"
                messages.append({"role": role, "content": text})

            chatbot_response = get_chatbot_response(messages)
            st.session_state.conversation.append(("소담", chatbot_response))
            st.write(f"소담: {chatbot_response}")

            # TTS로 챗봇 응답 재생
            audio_response = synthesize_speech(chatbot_response)
            if audio_response:
                play_audio(audio_response)

            # 대화 내용 업데이트
            display_conversation(st.session_state.conversation)

if __name__ == "__main__":
    main()
