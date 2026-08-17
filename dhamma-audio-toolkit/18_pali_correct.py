# -*- coding: utf-8 -*-
import re
# Legacy font map used by the Forest Dhamma PDFs -> proper Unicode
LEG = str.maketrans({'ã':'ā','õ':'ṇ','å':'ṭ','ï':'ī','ð':'ḍ'})
def deleg(s): return s.translate(LEG)

# Canonical spellings, taken from the books themselves
TERMS = ["samādhi","Nibbāna","mettā","viññāṇa","sīla","paññā","jhāna","anattā","avijjā",
 "sotāpanna","saññā","saṅkhāra","satipaṭṭhāna","anāgāmī","kammaṭṭhāna","vipassanā","vedanā",
 "paṭiccasamuppāda","pāṭimokkha","pīti","ānāpānasati","appanā","saddhā","brahmavihāra",
 "taṇhā","sakadāgāmī","upekkhā","upacāra","kilesa","kilesas","khandha","khandhas","citta",
 "dukkha","dhamma","saṅgha","bhikkhu","arahant","parikamma","buddho","dāna","nimitta","vinaya",
 "caṅkama","sukha","aniccā","upādāna","bhavaṅga","kiriya","sāmaggī","ajaan","paññāvaḍḍho"]

# Explicit mis-hearing -> canonical. Only entries that are NOT ordinary English.
SUBS = [
 (r'\bsome ?a?dhi\b|\bsamadhi\b|\bsamadis\b|\bsammati\b|\bsome oddity\b|\bsomatic\b(?=[^.]{0,40}\b(practice|mind|calm|jhana)\b)','samādhi'),
 (r'\bnibbana\b|\bnibana\b|\bnabano\b|\bnirvana\b','Nibbāna'),
 (r'\bvinnana\b|\bwinyana\b|\byou honou?r\b(?=[^.]{0,30}\bkhandha)','viññāṇa'),
 (r'\bsila\b|\bseela\b','sīla'),
 (r'\bpanya\b|\bpanyar\b|\bpanna\b(?!vaddho)','paññā'),
 (r'\bjhana\b|\bjana\b(?=[ ,.])','jhāna'),
 (r'\banatta\b','anattā'),
 (r'\bavijja\b','avijjā'),
 (r'\bsotapanna\b|\bcircuit panist\b','sotāpanna'),
 (r'\bsanna\b|\bsanya\b','saññā'),
 (r'\bsankhara(s?)\b',r'saṅkhāra\1'),
 (r'\bsatipatthana\b','satipaṭṭhāna'),
 (r'\bkammatt?h?ana\b|\bkamatana\b','kammaṭṭhāna'),
 (r'\bvipassana\b','vipassanā'),
 (r'\bvedana\b','vedanā'),
 (r'\bpaticcasamuppada\b|\bpatica ?samuppada\b','paṭiccasamuppāda'),
 (r'\bpatimokkha\b','pāṭimokkha'),
 (r'\bpiti\b|\bpt and so-?called\b','pīti'),
 (r'\banapanasati\b|\banapana\b','ānāpānasati'),
 (r'\btanha\b','taṇhā'),
 (r'\bupekkha\b','upekkhā'),
 (r'\bkeles(?:a|as|is)\b|\bchelac(?:e|es|is)\b|\bchelates\b|\bkeylaces\b|\bkelases\b|\bcollations?\b(?=[^.]{0,45}\b(mind|arise|overcome|practice)\b)','kilesas'),
 (r'\bkhandhas?\b|\bkundas\b|\bcandours\b','khandhas'),
 (r'\bparikamma\b|\bparacumb(?:ers)?\b|\bparacom\b|\bparakama?\b|\bpericum\b','parikamma'),
 (r'\bbuddho\b|\bpudhoe\b|\bbouto\b','Buddho'),
 (r'\bbikk?us?\b|\bbickel\b|\bbikrus\b',"bhikkhu"),
 (r'\barahants?\b|\barrow ?hunt(?:er|ers)\b|\baranant\b','arahant'),
 (r'\bcankama\b|\bchonkom\b|\bchantkama\b|\bjongrom\b','caṅkama'),
 (r'\bdana\b','dāna'),
 (r'\bthan ?a[ck]?ha?n mahã?a? ?bo+wa\b|\bdonald trump\b|\btuncha mahabore\b','Than Ajahn Mahā Boowa'),
 (r'\btan+a[ -]?chan+[ -]?man+\b|\btenetanman\b','Ajaan Mun'),
 (r'\bajahn pannavaddho\b|\bajaan panya\b','Ajaan Paññāvaḍḍho'),
]
def fix(t):
    n=0
    for pat,rep in SUBS:
        t,k=re.subn(pat,rep,t,flags=re.I); n+=k
    return t,n
if __name__=='__main__':
    import glob,sys
    tot=0; files=0
    for f in sorted(glob.glob('/tmp/tr/*.txt')):
        s=open(f).read(); s2,n=fix(s)
        if n: open(f,'w').write(s2); tot+=n; files+=1
    print("applied %d corrections across %d files"%(tot,files))
