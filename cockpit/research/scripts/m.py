from math import sqrt, ceil
M=1e-6
OP=dict(i=4*M,w=8*M,r=0.2*M,o=20*M); SO={k:v/2 for k,v in OP.items()}
HL=dict(i=.1*M,w=.2*M,r=.01*M,o=.5*M); HH={k:v*5 for k,v in HL.items()}
g,y,F,Fs=2779,519,72212,46630
def Cp(p,P,S,Ts=0,kR=0): return p['r']*P+p['o']*(S+Ts)+p['w']*(P-Fs)+kR*(p['r']*P+p['o']*y)
def Wstar(p,P,S,Ts=0,kR=0,q=0,g=g): return P+sqrt(2*g*Cp(p,P,S,Ts,kR)/(p['r']+q*p['w']))
def Acont(p,W,P,S,Ts=0,kR=0,q=0,g=g,y=y):
    x=W-P; C=Cp(p,P,S,Ts,kR)
    return p['r']*P+p['r']*x/2+p['w']*g+p['o']*y+p['r']*g+C*g/x+q*p['w']*(P+x/2-Fs)
def Astar(p,P,S,Ts=0,kR=0,q=0,g=g,y=y):
    C=Cp(p,P,S,Ts,kR); return p['r']*P+p['w']*g+p['o']*y+p['r']*g+sqrt(2*g*C*(p['r']+q*p['w']))+q*p['w']*(P-Fs)
def script(card,W,P,S,g=g,y=y,trig=None):
    # replicate measure_context.cycle_cost_per_request; card(ctx)->prices
    tot,ctx,n=0,P,0
    while ctx<W:
        p=card(ctx+g); tot+=p['r']*ctx+p['w']*g+p['o']*y; ctx+=g; n+=1
    p=card(W); tot+=p['r']*W+p['o']*S
    p=card(P); tot+=p['w']*(P-Fs)
    return tot/n,n
op=lambda c:OP; hk=lambda c: HH if c>100000 else HL
print("E1"); P=F+20000+25000; C=Cp(OP,P,20000); print(P,C, OP['r']*P,OP['o']*20000,OP['w']*(P-Fs))
W=Wstar(OP,P,20000); print("W*",W,"A*",Astar(OP,P,20000),"cont150",Acont(OP,150e3,P,20000),"cont967",Acont(OP,967e3,P,20000),"cont300",Acont(OP,300e3,P,20000))
for Wt in (150000,280000,285000,300000,967000): print(" script",Wt,script(op,Wt,P,20000))
print(" with Ts=y:",Wstar(OP,P,20000,Ts=y),Astar(OP,P,20000,Ts=y))
print("E2"); P=F+20000+50000; print(P,Cp(OP,P,20000),Wstar(OP,P,20000),Astar(OP,P,20000),"cont150",Acont(OP,150e3,P,20000),script(op,150000,P,20000))
print("E3"); P=F+10000; print(P,Cp(OP,P,10000),Wstar(OP,P,10000),Astar(OP,P,10000))
for Wt in (150000,200000,500000,967000): print(" script",Wt,script(op,Wt,P,10000)," cont",Acont(OP,Wt,P,10000))
print("E4"); I=OP['w']*g+OP['o']*y; print("I",I,"cx",I/OP['r'],[round(OP['r']*c+I,5) for c in (150e3,300e3,600e3,967e3)])
hc=lambda c,p:p['r']*c+p['w']*g+p['o']*y
print(" haiku",hc(99000,HL),hc(101000,HH),hc(101000,HH)/hc(99000,HL),hc(300000,HH),"cx haiku",(HL['w']*g+HL['o']*y)/HL['r'])
print("E5", (300000-Fs)*OP['w'], (300000-Fs)*OP['w']/hc(300000,OP), "(w-r) version",(300000-Fs)*(OP['w']-OP['r']))
P=F+45000; print(" idle", OP['r']*300000+OP['o']*20000+OP['w']*(P-Fs))
print("E6")
for q in (0,1/80,1/40,1/20): print(q,Wstar(OP,P,20000,q=q),Astar(OP,P,20000,q=q),Acont(OP,967e3,P,20000,q=q))
print("E7",Wstar(OP,P,20000,Ts=5000,g=3298),Astar(OP,P,20000,Ts=5000,g=3298,y=1038),Astar(OP,P,20000,Ts=5000,g=3298,y=1038)/Astar(OP,P,20000))
print("E8"); P=F+10000
for Wt in (95000,100000,150000,200000,300000,967000): print(" script haiku",Wt,script(hk,Wt,P,10000))
P=F+35000
best=min(((script(hk,Wt,P,10000)[0],Wt) for Wt in range(110000,1000001,5000))); print(" D25 best",best)
print("E9 raw", F+45000+sqrt(2*g*((F+45000)+20000+(F+45000-Fs))))
print("flat haiku low W*", Wstar(HL,F+10000,10000))
print("=== variants")
def cyc(card,P,S,n,Ts=0):
    tot=0
    for k in range(n):
        c=P+k*g; p=card(c+g); tot+=p['r']*c+p['w']*g+p['o']*y
    Wr=P+n*g; p=card(Wr); tot+=p['r']*Wr+p['o']*(S+Ts)
    p=card(P); tot+=p['w']*(P-Fs)
    return tot/n
P=F+45000
for n in (11,12): print("E1 150K n=",n,cyc(op,P,20000,n))
P=F+10000
for n in (5,6,7): print("E8 100K n=",n,cyc(hk,P,10000,n), "summary prompt",P+n*g)
for n in (24,25): print("E8 150K n=",n,cyc(hk,P,10000,n))
# continuous haiku 150K
print("=== sensitivity")
P=F+45000
gm,ym=3552,1334
print("means: W*",Wstar(OP,P,20000,g=gm),"A*",Astar(OP,P,20000,g=gm,y=ym),"cx",(OP['w']*gm+OP['o']*ym)/OP['r'])
print("model pred at mean ctx 183194 medians",OP['r']*183194+I, "means",OP['r']*183194+OP['w']*3650+OP['o']*ym, "observed",7.5531/71)
Fs2=F
C2=OP['r']*P+OP['o']*20000+OP['w']*(P-Fs2); print("Fs=F: C'",C2,"W*",P+sqrt(2*g*C2/OP['r']))
for k in (1.25,1.5,2,5.13): print("flatness k",k,(k+1/k)/2)
