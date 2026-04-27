import re
SRC = "/opt/lera-build/src"

# ── 1. leraApi.ts ─────────────────────────────────────────────────────────
open(f"{SRC}/lib/leraApi.ts","w").write(
    'function getInitData(){try{return(window as any).Telegram?.WebApp?.initData||"";}catch{return "";}}\n'
    'async function _req<T>(p:string,o:RequestInit={}):Promise<T|null>{'
    'try{const r=await fetch(p,{...o,headers:{"Content-Type":"application/json","X-Init-Data":getInitData(),...(o.headers||{})}});'
    'if(!r.ok)return null;return r.json();}catch{return null;}}\n'
    'export function leraApi<T=any>(path:string,opts?:RequestInit):Promise<T|null>{return _req<T>(path,opts);}\n'
    'leraApi.get=<T=any>(p:string)=>_req<T>(p);\n'
    'leraApi.del=<T=any>(p:string)=>_req<T>(p,{method:"DELETE"});\n'
    'leraApi.upload=async<T=any>(p:string,fd:FormData):Promise<T|null>=>'
    '{try{const r=await fetch(p,{method:"POST",headers:{"X-Init-Data":getInitData()},body:fd});'
    'if(!r.ok)return null;return r.json();}catch{return null;}};\n'
    'export async function leraUpload(f:File):Promise<string|null>{'
    'try{const fd=new FormData();fd.append("file",f);'
    'const r=await fetch("/api/upload",{method:"POST",headers:{"X-Init-Data":getInitData()},body:fd});'
    'if(!r.ok)return null;return(await r.json()).url||null;}catch{return null;}}\n'
    'export async function leraFetch(p:string,o:RequestInit={}):Promise<Response>{'
    'return fetch(p,{...o,headers:{"X-Init-Data":getInitData(),...(o.headers||{})}})}\n'
    'export interface MeResponse{tg_id:number;is_admin?:boolean;gender?:string;'
    'nesso_balance?:number;is_vip?:boolean;[k:string]:any;}\n'
)
print("leraApi.ts OK")

# ── 2. ProfilePage: lazy sub-pages ────────────────────────────────────────
with open(f"{SRC}/pages/ProfilePage.tsx") as f:
    code = f.read()
if 'import PremiumPage from' in code:
    code = code.replace(
        'import { useState, useRef, useEffect } from "react";',
        'import { useState, useRef, useEffect, lazy, Suspense } from "react";'
    )
    for p in ['PremiumPage','HelpPage','ShopPage','GachaPage']:
        code = re.sub(f'import {p} from "@/pages/{p}";', f'const {p}=lazy(()=>import("@/pages/{p}"));', code)
    for p in ['Premium','Help','Shop','Gacha']:
        code = code.replace(
            f'{{show{p} && <{p}Page onClose={{()=>setShow{p}(false)}} />}}',
            f'<Suspense fallback={{null}}>{{show{p} && <{p}Page onClose={{()=>setShow{p}(false)}} />}}</Suspense>'
        )
    open(f"{SRC}/pages/ProfilePage.tsx","w").write(code)
print("ProfilePage.tsx OK")

# ── 3. ShopPage: lazy GachaPage ───────────────────────────────────────────
with open(f"{SRC}/pages/ShopPage.tsx") as f:
    code = f.read()
if 'import GachaPage from' in code:
    code = code.replace(
        'import GachaPage from "@/pages/GachaPage";',
        'import { lazy, Suspense } from "react";\nconst GachaPage=lazy(()=>import("@/pages/GachaPage"));'
    )
    open(f"{SRC}/pages/ShopPage.tsx","w").write(code)
print("ShopPage.tsx OK")

# ── 4. PartnerPage ────────────────────────────────────────────────────────
with open(f"{SRC}/pages/PartnerPage.tsx") as f:
    code = f.read()

# 4a. Remove DuoProfileEditor
code = re.sub(r'import \{ DuoProfileEditor \} from "[^"]+";?\n?', '', code)
code = code.replace(
    '<DuoProfileEditor inline />',
    '<div className="p-4 text-center text-white/50 text-sm">Анкету настройте в Профиле</div>'
)

# 4b. TDZ fix — move filters block BEFORE const [apiCards
if 'type DuetFilters' in code and 'const [apiCards' in code:
    try:
        s = code.index('  type DuetFilters')
        e_start = code.index('  const filterCount', s)
        e_end = code.index('\n', e_start) + 1
        block = code[s:e_end]
        code = code[:s] + code[e_end:]
        anchor = '  const [apiCards'
        code = code[:code.index(anchor)] + block + code[code.index(anchor):]
        print("  TDZ filters fix OK")
    except Exception as ex:
        print(f"  TDZ fix skipped: {ex}")

# 4c. Replace MatchHistoryTab — API-backed, bigger cards, correct time
NEW_TAB = r'''function MatchHistoryTab() {
  const [likes, setLikes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    import("@/lib/leraApi").then(({ leraApi }) => {
      leraApi<{ likes: any[] }>("/api/duet/likes")
        .then(r => { if (r?.likes) setLikes(r.likes); setLoading(false); });
    });
  }, []);
  function timeAgo(ts: string) {
    const diff = Date.now() - new Date(ts.replace(" ","T")+"Z").getTime();
    const m=Math.floor(diff/60000),h=Math.floor(diff/3600000),d=Math.floor(diff/86400000);
    if(m<1)return"только что";if(m<60)return`${m} мин назад`;if(h<24)return`${h} ч назад`;return`${d} д назад`;
  }
  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <div className="text-white/30 text-sm">Загрузка…</div>
    </div>
  );
  if (likes.length===0) return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-center px-6">
      <img src="/lera-chibi.jpg" alt="Лера" className="w-16 h-16 object-contain opacity-40" />
      <h3 className="font-bold text-foreground">Лайков пока нет</h3>
      <p className="text-sm text-muted-foreground">Когда кто-то лайкнет тебя — появится здесь</p>
    </div>
  );
  return (
    <div className="p-3 space-y-3">
      {likes.map(u=>{
        let photos:string[]=[]; try{photos=u.profile_photos?JSON.parse(u.profile_photos):[];}catch{}
        const av=u.custom_avatar||photos[0]||u.tg_photo_url||"";
        return(
          <div key={u.from_tg_id} className="bg-[#13131a] border border-white/8 rounded-3xl overflow-hidden shadow-xl">
            <div className="aspect-[4/3] relative bg-gradient-to-br from-primary/20 to-transparent flex items-end">
              {av
                ?<img src={av} alt="" className="absolute inset-0 w-full h-full object-cover"/>
                :<div className="absolute inset-0 flex items-center justify-center text-6xl">🎮</div>}
              <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent"/>
              <div className="relative p-4 w-full">
                <div className="flex items-baseline gap-2">
                  <h3 className="text-xl font-black text-white">{u.nickname||"Игрок"}</h3>
                  {u.age?<span className="text-white/60 text-lg">{u.age}</span>:null}
                </div>
                {u.city&&<p className="text-sm text-white/60">📍 {u.city}</p>}
              </div>
            </div>
            <div className="p-4 flex items-center justify-between">
              <span className="text-xs text-white/30">{timeAgo(u.created_at)}</span>
              <span className="text-xs bg-pink-500/15 border border-pink-500/30 text-pink-300 px-3 py-1 rounded-full font-semibold">❤️ Лайкнул тебя</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
'''
if 'function MatchHistoryTab()' in code:
    code = re.sub(
        r'function MatchHistoryTab\(\).*?(?=\nconst COUNTRY_FLAGS)',
        NEW_TAB,
        code, flags=re.DOTALL
    )
    print("  MatchHistoryTab -> API OK")

open(f"{SRC}/pages/PartnerPage.tsx","w").write(code)
print("PartnerPage.tsx OK")

# ── 5. vite.config.ts: single chunk ──────────────────────────────────────
with open("/opt/lera-build/vite.config.ts") as f:
    vite = f.read()
if 'manualChunks' not in vite:
    vite = vite.replace(
        'emptyOutDir: true,',
        'emptyOutDir: true,\n    rollupOptions:{output:{manualChunks:()=>"index"}},'
    )
    open("/opt/lera-build/vite.config.ts","w").write(vite)
print("vite.config.ts OK")
