import os,sys,glob,io,json,subprocess
import numpy as np, soundfile as sf, sherpa_onnx
SHARD=int(sys.argv[1]); N=int(sys.argv[2])
M='/tmp/sherpa-onnx-whisper-small.en/'
rec=sherpa_onnx.OfflineRecognizer.from_whisper(encoder=M+'small.en-encoder.int8.onnx',
    decoder=M+'small.en-decoder.int8.onnx',tokens=M+'small.en-tokens.txt',num_threads=1)
vids=sorted(glob.glob('/tmp/qa/*.mp4')+glob.glob('/tmp/final/*.mp4')+glob.glob('/tmp/out_solo/*.mp4'))
for k,v in enumerate(vids):
    if k%N!=SHARD: continue
    out='/tmp/tr/'+os.path.splitext(os.path.basename(v))[0]+'.txt'
    if os.path.exists(out): continue
    wav=subprocess.run(['ffmpeg','-v','error','-i',v,'-ac','1','-ar','16000','-f','wav','-'],
                       capture_output=True).stdout
    try: x,sr=sf.read(io.BytesIO(wav),dtype='float32')
    except Exception: continue
    # chunk at the quietest point near every 24 s, hard cap 28 s (whisper limit)
    H=int(0.025*sr); nf=len(x)//H
    e=np.sqrt((x[:nf*H].reshape(nf,H)**2).mean(1))
    dur=len(x)/sr; cuts=[0.0]; t=0.0
    while t<dur-1.0:
        tgt=min(t+24.0,dur)
        if dur-tgt<4.0: cuts.append(dur); break
        lo,hi=int((tgt-3.0)/0.025),min(int((tgt+3.0)/0.025),nf)
        ct=(lo+int(np.argmin(e[lo:hi])))*0.025 if hi>lo else tgt
        if ct<=t+5: ct=tgt
        cuts.append(round(ct,3)); t=ct
    if cuts[-1]<dur: cuts.append(round(dur,3))
    lines=[]
    for i in range(len(cuts)-1):
        s0,s1=cuts[i],min(cuts[i+1],cuts[i]+28.0)
        seg=x[int(s0*sr):int(s1*sr)]
        if len(seg)<int(0.2*sr): continue
        st=rec.create_stream(); st.accept_waveform(sr,seg); rec.decode_stream(st)
        txt=st.result.text.strip()
        if txt: lines.append((s0,s1,txt))
    with open(out+'.part','w') as f:
        for s0,s1,txt in lines:
            f.write("[%02d:%02d] %s\n"%(int(s0)//60,int(s0)%60,txt))
    os.replace(out+'.part',out)
    print("done",os.path.basename(out),flush=True)
