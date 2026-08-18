import numpy as np, wave, subprocess, glob, os, re, sys, io
import sherpa_onnx
M='/tmp/claude-0/-home-user-claude-code/a2158284-aaa7-5636-a736-2b61262780bf/scratchpad/sherpa-onnx-whisper-base.en/'
r=sherpa_onnx.OfflineRecognizer.from_whisper(encoder=M+'base.en-encoder.int8.onnx',
    decoder=M+'base.en-decoder.int8.onnx',tokens=M+'base.en-tokens.txt',num_threads=4)
firsts={}
for d in ('/tmp/qa','/tmp/final','/tmp/out_solo'):
    for f in sorted(glob.glob(d+'/*.mp4')):
        b=os.path.basename(f)
        key=re.sub(r'_(part\d+_of_\d+|\d+)\.mp4$','',b)
        if key not in firsts: firsts[key]=f
for key in sorted(firsts):
    f=firsts[key]
    w=subprocess.run(['ffmpeg','-v','error','-t','90','-i',f,'-ac','1','-ar','16000',
                      '-f','wav','-'],capture_output=True).stdout
    x,sr=__import__('soundfile').read(io.BytesIO(w),dtype='float32')
    out=[]
    for t0 in (0,30,60):
        seg=x[t0*sr:(t0+28)*sr]
        if len(seg)<sr: break
        s=r.create_stream(); s.accept_waveform(sr,seg); r.decode_stream(s)
        out.append(s.result.text.strip())
    print("### %s\n%s\n"%(key," ".join(out)[:520]),flush=True)
