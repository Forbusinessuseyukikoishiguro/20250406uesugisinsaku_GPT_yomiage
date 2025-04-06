import os
import sys
from pathlib import Path
from openai import OpenAI
import pygame
import time
import threading
import queue

# 音声ファイルを管理するためのキュー
audio_queue = queue.Queue()
# 再生状態を管理するフラグ
is_playing = False
# 音声カウンタ
speech_counter = 0

# Pygameの音声ミキサーを初期化
pygame.mixer.init()


def validate_api_key():
    """APIキーの存在を確認"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("🚨 エラー: OpenAI APIキーが設定されていません。")
        print("環境変数OPENAI_API_KEYにAPIキーを設定してください。")
        print("例:")
        print("Windows PowerShell: $env:OPENAI_API_KEY='your-api-key'")
        print("macOS/Linux: export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)
    return api_key


def text_to_speech(
    text,
    voice="onyx",
    instructions="上杉武将のような、重厚で知的な声で話してください",
    play_immediately=True,
):
    """
    GPT-4o-mini-ttsを使用してテキストを音声に変換

    引数:
    - text: 音声に変換するテキスト
    - voice: 使用する音声（デフォルト: onyx）
    - instructions: 音声の話し方指示
    - play_immediately: 生成後すぐに再生するかどうか

    戻り値:
    - 音声ファイルのパス
    """
    global speech_counter

    try:
        # APIキーの検証
        validate_api_key()

        # OpenAIクライアントの初期化
        client = OpenAI()

        # 音声ファイルに一意の名前を付ける
        speech_counter += 1
        speech_file_path = Path(__file__).parent / f"speech_{speech_counter}.mp3"

        # 音声生成のリクエスト（ストリーミングモード）
        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts", voice=voice, input=text, instructions=instructions
        ) as response:
            # ストリーミングデータをファイルに保存
            with open(speech_file_path, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)

            # キューに追加
            audio_info = {"path": str(speech_file_path), "text": text}
            audio_queue.put(audio_info)

            print(f"✅ 音声ファイルが生成されました: {speech_file_path}")

            # 再生スレッドが動いていなければ開始
            start_playback_thread()

            return speech_file_path

    except Exception as e:
        print(f"🚨 音声生成中にエラーが発生: {e}")
        return None


def playback_thread_function():
    """音声再生を担当するスレッド関数"""
    global is_playing

    is_playing = True

    while True:
        try:
            if not audio_queue.empty():
                # キューから次の音声を取得
                audio_info = audio_queue.get()

                # 音声ファイルのパスを取得
                file_path = audio_info["path"]

                print(f"🔊 再生中: 「{audio_info['text'][:30]}...」")

                # 音声を再生
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()

                # 再生が終わるまで待機
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)

                # キュータスクの完了を通知
                audio_queue.task_done()
            else:
                # キューが空の場合は少し待機
                time.sleep(0.5)

                # 一定時間キューが空ならスレッドを終了
                if audio_queue.empty():
                    is_playing = False
                    break

        except Exception as e:
            print(f"🚨 音声再生中にエラーが発生: {e}")

    is_playing = False


def start_playback_thread():
    """音声再生スレッドを開始（必要な場合のみ）"""
    global is_playing

    if not is_playing:
        playback_thread = threading.Thread(target=playback_thread_function)
        playback_thread.daemon = True  # メインスレッド終了時に一緒に終了
        playback_thread.start()


def process_batch_text(text_list, voice="onyx", instructions=""):
    """
    複数のテキストを一括で処理

    引数:
    - text_list: 処理するテキストのリスト
    - voice: 使用する音声
    - instructions: 話し方の指示
    """
    for text in text_list:
        text_to_speech(text, voice, instructions, play_immediately=True)
        # APIレート制限を考慮して少し待機
        time.sleep(0.5)


def main():
    """メインの対話ループ"""
    print("🎙️ 上杉武将風 音声生成システム")
    print(
        "利用可能な声: Alloy, Ash, Ballad, Coral, Echo, Fable, Onyx, Nova, Sage, Shimmer, Verse"
    )
    print(
        "💡 ヒント: 複数のテキストを連続処理するには、各文を改行で区切って入力し、最後に空行を入力してください。"
    )

    # 音声と話し方の初期設定
    current_voice = "onyx"
    current_instructions = "上杉武将のような、重厚で知的な声で話してください。低く落ち着いた声で、一語一語に深い意味を込めてください。"

    # 設定メニューを表示
    def show_settings():
        print("\n⚙️ 現在の設定:")
        print(f"🔊 音声: {current_voice}")
        print(f"📝 話し方: {current_instructions}")

    while True:
        try:
            show_settings()

            # マルチライン入力モードの説明
            print(
                "\n📜 テキストを入力してください (複数行の場合は空行で終了、終了するには 'exit'):"
            )

            # 複数行のテキスト入力を受け付ける
            lines = []
            while True:
                line = input()
                if line.lower() in ["exit", "退く"]:
                    if not lines:  # exitのみの入力の場合はプログラム終了
                        print("🏯 音声生成システムを終了します。")
                        return
                    break
                elif not line and lines:  # 空行で入力終了
                    break
                elif line:
                    lines.append(line)

            # 入力がなければ次のループへ
            if not lines:
                continue

            # 設定を変更するかどうか
            change_settings = (
                input("⚙️ 設定を変更しますか？ (y/n, デフォルト: n): ").lower() == "y"
            )

            if change_settings:
                # 音声の種類を選択
                new_voice = input(f"🔊 使用する声 (現在: {current_voice}): ")
                if new_voice:
                    current_voice = new_voice

                # 話し方の指示を入力
                new_instructions = input(
                    f"📝 話し方の指示 (現在の設定をそのまま使うには空欄): "
                )
                if new_instructions:
                    current_instructions = new_instructions

            # 複数行のテキストを処理
            if len(lines) == 1:
                # 単一行の場合は通常処理
                text_to_speech(lines[0], current_voice, current_instructions)
            else:
                # 複数行の場合は一括処理
                print(f"🔄 {len(lines)}件のテキストを連続処理します...")
                process_batch_text(lines, current_voice, current_instructions)

        except KeyboardInterrupt:
            print("\n🚪 操作を中断しました。")
            break
        except Exception as e:
            print(f"🚨 予期せぬエラーが発生: {e}")


# スクリプトの実行
if __name__ == "__main__":
    main()

"""
音声生成のための準備:

1. 必要なライブラリをインストール
pip install openai pygame

2. OpenAI APIキーを設定
Windows PowerShell: $env:OPENAI_API_KEY='your-api-key'
macOS/Linux: export OPENAI_API_KEY='your-api-key'

3. スクリプトを実行
python voice_generator.py
"""
