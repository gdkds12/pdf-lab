import wave
import struct

# Create a 5-second silent WAV file
duration = 5
sample_rate = 44100
num_frames = duration * sample_rate
num_channels = 1
sample_width = 2  # 16-bit

with wave.open("backend/sample.wav", "w") as f:
    f.setnchannels(num_channels)
    f.setsampwidth(sample_width)
    f.setframerate(sample_rate)
    # Write 0s
    data = struct.pack('<h', 0) * num_frames
    f.writeframes(data)

print("Created backend/sample.wav")
