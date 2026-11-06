M=1e-6; r,w,o=0.2*M,8*M,20*M
g,y,F,Fs=2779,519,72212,46630
S,D=20000,25000; P=F+S+D
I=w*g+o*y
Crew=w*(P-Fs)
def A(W,q,T=200000,idle=True,cold='w'):
    # renewal-reward: cycle starts at P; each progress request k at c=P+k g
    # before request k>0 with prob q an idle gap: if idle and c>=T -> idle compaction ends cycle (before request)
    surv=1.0; cost=0.0; reqs=0.0; k=0
    while True:
        c=P+k*g
        if c>=W:  # auto compaction
            cost+=surv*(r*c+o*S+Crew); break
        if k>0:
            if idle and c>=T:
                cost+=surv*q*(r*c+o*S+Crew); surv*=(1-q)
            else:
                extra=(w if cold=='w' else (w-r))*(c-Fs)
                cost+=surv*q*extra
        cost+=surv*(r*c+I); reqs+=surv; k+=1
    return cost/reqs
for q in (0,1/80,1/40,1/20):
    grid={W:A(W,q) for W in range(150000,1000001,5000)}
    b=min(grid,key=grid.get)
    off={W:A(W,q,idle=False) for W in range(150000,1000001,5000)}
    bo=min(off,key=off.get)
    print(f"q={q:.4f} idle-on: best {b} ${grid[b]:.4f} 967K ${A(967000,q):.4f} 235K ${A(235000,q):.4f} | idle-off: best {bo} ${off[bo]:.4f} 967K ${off[965000]:.4f}")
