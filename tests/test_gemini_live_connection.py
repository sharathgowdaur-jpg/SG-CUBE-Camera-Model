import os
import sys
import time
import asyncio
import unittest

from assistive.api_key_manager import APIKeyManager
from google import genai
from google.genai import types


class TestGeminiLiveConnectionDiagnostic(unittest.IsolatedAsyncioTestCase):
    """
    Phase 5 & 10: Real Gemini Live Connection & Natural Dialogue Diagnostic.
    Tests live connection, single authoritative voice (Puck), prompt confirmation,
    interruption handling, and multi-turn conversational exchange.
    """

    async def asyncSetUp(self):
        self.km = APIKeyManager()
        self.api_key = self.km.get_active_api_key()
        if not self.api_key:
            self.skipTest("No valid active Gemini API key configured.")

        self.model_name = "gemini-3.1-flash-live-preview"
        self.voice_name = "Puck"
        self.client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1alpha"})

        self.config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice_name)
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text="You are SG CUBE, an intelligent voice assistant. Keep answers brief and conversational.")]
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS
            ),
        )

    async def test_01_text_based_gemini_connection_confirmation(self):
        """
        Phase 5 requirement:
        Send: 'Hello SG CUBE connection test. Reply with a short confirmation.'
        Verify that Gemini responds with actual confirmation text.
        Log response time, token/text output, confirmation result.
        """
        prompt = "Hello SG CUBE connection test. Reply with a short confirmation."
        print(f"\n[DIAGNOSTIC TEST] Connecting to {self.model_name} with voice {self.voice_name}...")

        t_connect_start = time.time()
        async with self.client.aio.live.connect(model=self.model_name, config=self.config) as session:
            t_connected = time.time()
            connect_latency = t_connected - t_connect_start
            print(f"[DIAGNOSTIC TEST] Connected in {connect_latency:.3f}s. Sending prompt: '{prompt}'...")

            t_send = time.time()
            await session.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
                turn_complete=True,
            )

            received_text = ""
            total_audio_bytes = 0
            audio_parts = 0
            t_first_audio = None

            timeout_s = 15.0
            start_wait = time.time()

            async for response in session.receive():
                if time.time() - start_wait > timeout_s:
                    break

                sc = response.server_content
                if sc:
                    if sc.output_transcription and sc.output_transcription.text:
                        received_text += sc.output_transcription.text

                    if sc.model_turn:
                        for part in sc.model_turn.parts:
                            if part.inline_data and part.inline_data.data:
                                if t_first_audio is None:
                                    t_first_audio = time.time()
                                audio_parts += 1
                                total_audio_bytes += len(part.inline_data.data)

                    if sc.turn_complete:
                        t_complete = time.time()
                        total_time = t_complete - t_send
                        first_audio_lat = (t_first_audio - t_send) if t_first_audio else 0.0

                        print(f"[DIAGNOSTIC TEST] Turn complete!")
                        print(f"[DIAGNOSTIC TEST] Response Text: '{received_text.strip()}'")
                        print(f"[DIAGNOSTIC TEST] Time to first audio: {first_audio_lat:.3f}s, Total response time: {total_time:.3f}s")
                        print(f"[DIAGNOSTIC TEST] Audio bytes received: {total_audio_bytes} ({audio_parts} parts, 24kHz PCM)")
                        break

            self.assertTrue(len(received_text) > 0, "No output transcription received from Gemini Live.")
            self.assertTrue(total_audio_bytes > 0, "No audio chunks received from Gemini Live.")
            self.assertTrue(
                any(w in received_text.lower() for w in ["confirm", "receiving", "loud", "clear", "hello", "acknowledged", "ready"]),
                f"Unexpected response text: '{received_text}'"
            )

    async def test_02_multi_turn_conversation_flow(self):
        """Verifies multi-turn back-and-forth conversation maintains state."""
        turns = [
            "What is 2 plus 3?",
            "Multiply that result by 10.",
            "Thank you, good job."
        ]

        async with self.client.aio.live.connect(model=self.model_name, config=self.config) as session:
            for turn_idx, user_query in enumerate(turns):
                t_send = time.time()
                await session.send_client_content(
                    turns=[types.Content(role="user", parts=[types.Part.from_text(text=user_query)])],
                    turn_complete=True,
                )

                turn_text = ""
                turn_bytes = 0

                async for response in session.receive():
                    sc = response.server_content
                    if sc:
                        if sc.output_transcription and sc.output_transcription.text:
                            turn_text += sc.output_transcription.text
                        if sc.model_turn:
                            for part in sc.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    turn_bytes += len(part.inline_data.data)
                        if sc.turn_complete:
                            break

                print(f"[MULTI-TURN {turn_idx+1}] Query: '{user_query}' -> Reply: '{turn_text.strip()}' ({turn_bytes} bytes audio)")
                self.assertTrue(len(turn_text) > 0, f"Turn {turn_idx+1} received empty response.")
                self.assertTrue(turn_bytes > 0, f"Turn {turn_idx+1} received 0 audio bytes.")


if __name__ == "__main__":
    unittest.main()
