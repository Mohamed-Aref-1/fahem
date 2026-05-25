import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import NeuralBrain from '../components/NeuralBrain'
import FloatingChat from '../components/FloatingChat'

/* ─────────────────────────────────────────────
   Animated phone mockup
───────────────────────────────────────────── */
function AnimatedPhone() {
  const [phase, setPhase] = useState(0)

  useEffect(() => {
    let ts = []
    const run = () => {
      setPhase(0)
      ts.push(setTimeout(() => setPhase(1), 600))
      ts.push(setTimeout(() => setPhase(2), 1900))
      ts.push(setTimeout(() => setPhase(3), 2700))
      ts.push(setTimeout(() => setPhase(4), 3700))
    }
    run()
    const id = setInterval(() => { ts.forEach(clearTimeout); ts = []; run() }, 6500)
    return () => { ts.forEach(clearTimeout); clearInterval(id) }
  }, [])

  const msg = (n) => ({
    opacity:   phase >= n ? 1 : 0,
    transform: phase >= n ? 'translateY(0)' : 'translateY(10px)',
    transition: 'opacity 0.45s ease, transform 0.45s ease',
  })

  return (
    /* outer wrapper: rotation handled here so float only needs translateY */
    <div className="relative mx-auto w-[300px]">
      <div
        className="phone-float relative w-[300px] h-[620px]"
        style={{
          borderRadius: '50px',
          background: 'linear-gradient(155deg, #e8e8e8 0%, #aaa 40%, #d4d4d4 70%, #b8b8b8 100%)',
          padding: '3px',
          boxShadow: '0 32px 84px rgba(22,47,102,0.4), 0 2px 8px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.6)',
        }}
      >
        {/* inner black bezel */}
        <div className="w-full h-full" style={{ borderRadius: '47px', overflow: 'hidden', background: '#111' }}>

        {/* screen */}
        <div className="w-full h-full flex flex-col relative" style={{ borderRadius: '47px', overflow: 'hidden', backgroundImage: 'url(/whatsapp_bg.jpeg)', backgroundSize: 'cover', backgroundPosition: 'center' }} dir="rtl">

          {/* Dynamic Island */}
          <div className="absolute z-20" style={{ top: '14px', left: '50%', transform: 'translateX(-50%)' }}>
            <div style={{ width: '110px', height: '32px', background: '#000', borderRadius: '20px' }} />
          </div>

          {/* header */}
          <div className="text-white px-4 py-3 flex items-center gap-2.5 shrink-0"
            style={{ background: 'linear-gradient(to right, #162F66, #1e3f8a)', paddingTop: '52px' }}>
            <img src="/logo.png" alt="فاهم" className="w-9 h-9 rounded-full object-cover shrink-0 shadow" />
            <div className="flex-1">
              <div className="font-bold text-xs">فاهم | Fahim</div>
              <div className="text-[9px] flex items-center gap-1" style={{ color: 'rgba(255,255,255,0.85)' }}>
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block"></span> متصل الآن
              </div>
            </div>
            <div className="text-[9px] font-semibold px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(255,255,255,0.15)' }}>
              🇪🇬 🇸🇦 🇦🇪
            </div>
          </div>

          {/* messages */}
          <div className="flex-1 px-3 pt-3 pb-1 flex flex-col gap-2.5 overflow-hidden">

            {/* bot greeting */}
            <div style={msg(1)} className="flex items-end gap-1.5">
              <img src="/logo.png" alt="فاهم" className="w-6 h-6 rounded-full object-cover shrink-0 shadow-sm" />
              <div className="bg-white rounded-tl-none rounded-tr-xl rounded-b-xl px-3 py-2 text-[10px] shadow-sm max-w-[80%] leading-relaxed">
                أهلاً! أنا فاهم 👋<br />اسألني عن أي منتج على نون وهرشحلك الأحسن 🎯
              </div>
            </div>

            {/* user message */}
            <div style={msg(2)} className="flex justify-start">
              <div className="bg-[#DCF8C6] rounded-tr-none rounded-tl-xl rounded-b-xl px-3 py-2 text-[10px] shadow-sm max-w-[78%] self-end ml-auto">
                عايز تكييف لأوضة 20 متر
              </div>
            </div>

            {/* typing indicator */}
            {phase === 3 && (
              <div className="flex items-end gap-1.5">
                <div className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center text-xs"
                  style={{ background: 'linear-gradient(135deg,#D4A500,#F0C040)' }}>🤖</div>
                <div className="bg-white rounded-tl-none rounded-tr-xl rounded-b-xl px-3 py-2.5 shadow-sm inline-block">
                  <div className="typing-dots"><div className="typing-dot"/><div className="typing-dot"/><div className="typing-dot"/></div>
                </div>
              </div>
            )}

            {/* bot reply */}
            <div style={msg(4)} className="flex items-end gap-1.5">
              <img src="/logo.png" alt="فاهم" className="w-6 h-6 rounded-full object-cover shrink-0 shadow-sm" />
              <div className="bg-white rounded-tl-none rounded-tr-xl rounded-b-xl px-3 py-2 text-[10px] shadow-sm max-w-[80%] leading-relaxed">
                تمام! بناءً على 20 م² هتحتاج 1.5 حصان. دي أفضل خيارات 👇
              </div>
            </div>

            {/* product card */}
            <div style={{ ...msg(4), transitionDelay: '180ms' }} className="mr-8 bg-white rounded-xl overflow-hidden shadow-md border border-gray-100">
              <div className="flex items-center gap-2 px-3 py-2" style={{ background: 'linear-gradient(to right,#EFF6FF,#DBEAFE)' }}>
                <span className="text-base">❄️</span>
                <div className="flex-1">
                  <div className="font-bold text-[10px] text-gray-900">LG دوال إنفرتر 1.5 حصان</div>
                  <div className="text-[8px] text-gray-500">✓ إنفرتر  ✓ ضمان 5 سنين</div>
                </div>
                <div className="text-[8px] font-bold text-white px-1.5 py-0.5 rounded-full" style={{ background: '#D4A500' }}>الأفضل</div>
              </div>
              <div className="px-3 py-2 flex items-center justify-between">
                <div>
                  <div className="text-red-600 font-bold text-[11px]">12,999 ج.م</div>
                  <div className="text-[8px] text-gray-400">⭐ 4.8 · 1,240 تقييم</div>
                </div>
                <div className="text-[8px] font-bold text-white px-2 py-0.5 rounded-full" style={{ background: '#162F66' }} dir="ltr">FAHIM20</div>
              </div>
            </div>
          </div>

          {/* input */}
          <div className="bg-[#f0f2f5] px-2 py-2 flex items-center gap-1.5 pb-5 shrink-0">
            <div className="w-7 h-7 rounded-full bg-[#162F66] flex items-center justify-center text-white">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style={{ transform: 'rotate(180deg) translateX(-1px)' }}><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
            </div>
            <div className="flex-1 bg-white rounded-full h-7 flex items-center px-3 text-[10px] text-gray-400">اكتب هنا...</div>
          </div>
        </div>
        </div>

        {/* iPhone 15 side buttons */}
        {/* Action button */}
        <div className="absolute" style={{ left: '-4px', top: '78px', width: '4px', height: '28px', background: 'linear-gradient(to right, #888, #c8c8c8)', borderRadius: '3px 0 0 3px' }} />
        {/* Volume up */}
        <div className="absolute" style={{ left: '-4px', top: '122px', width: '4px', height: '40px', background: 'linear-gradient(to right, #888, #c8c8c8)', borderRadius: '3px 0 0 3px' }} />
        {/* Volume down */}
        <div className="absolute" style={{ left: '-4px', top: '172px', width: '4px', height: '40px', background: 'linear-gradient(to right, #888, #c8c8c8)', borderRadius: '3px 0 0 3px' }} />
        {/* Power button */}
        <div className="absolute" style={{ right: '-4px', top: '135px', width: '4px', height: '76px', background: 'linear-gradient(to left, #888, #c8c8c8)', borderRadius: '0 3px 3px 0' }} />
        {/* USB-C port */}
        <div className="absolute" style={{ bottom: '10px', left: '50%', transform: 'translateX(-50%)', width: '50px', height: '6px', background: '#666', borderRadius: '3px' }} />
      </div>

      {/* floating badges */}
      <div className="absolute top-16 -left-14 bg-white px-3 py-2.5 rounded-2xl shadow-xl animate-bounce z-10" style={{ animationDuration: '3s' }}>
        <div className="text-xl mb-0.5">💸</div>
        <div className="text-[11px] font-bold text-gray-800">كوبونات حصرية</div>
        <div className="text-[9px] text-gray-500 mt-0.5">خصم حتى 10%</div>
      </div>
      <div className="absolute bottom-28 -left-14 bg-white px-3 py-2.5 rounded-2xl shadow-xl animate-bounce z-10" style={{ animationDuration: '4s', animationDelay: '1s' }} dir="rtl">
        <div className="text-xl mb-0.5">⚡</div>
        <div className="text-[11px] font-bold text-gray-800">رد في 3 ثواني</div>
        <div className="text-[9px] text-gray-500 mt-0.5">24/7</div>
      </div>
      <div className="absolute top-60 -right-10 bg-white px-3 py-2.5 rounded-2xl shadow-xl z-10" dir="rtl"
        style={{ animation: 'bounce 5s ease-in-out 0.5s infinite' }}>
        <div className="text-xl mb-0.5">🇪🇬🇸🇦🇦🇪</div>
        <div className="text-[9px] font-bold text-gray-700">٣ دول على نون</div>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────
   Marquee trust bar
───────────────────────────────────────────── */
const TRUST_ITEMS = [
  '🇪🇬 متاح في مصر',
  '🇸🇦 متاح في السعودية',
  '🇦🇪 متاح في الإمارات',
  '🛒 يشتغل مع Noon.com',
  '🎁 كوبونات خصم حصرية',
  '⚡ رد فوري في ثواني',
  '🔍 بيتجاهل الإعلانات المدفوعة',
  '10M+ منتج في قاعدة البيانات',
]

function TrustMarquee() {
  const items = [...TRUST_ITEMS, ...TRUST_ITEMS]
  return (
    <div className="overflow-hidden bg-primary/5 border-b border-border/50 py-2" dir="ltr">
      <div className="marquee-track">
        {items.map((item, i) => (
          <span key={i} className="inline-flex items-center gap-1 mx-6 text-xs font-semibold text-primary/80 shrink-0">
            {item}
            <span className="mx-3 text-border">·</span>
          </span>
        ))}
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────
   Live demo data — 3 conversations cycling
───────────────────────────────────────────── */
const CONVERSATIONS = [
  {
    flag: '🇸🇦', country: 'السعودية',
    userMsg: 'عايز سماعة للمواصلات — خفيفة وبطارية تدوم',
    botMsg: 'وجدت التوصية المثالية! Sony WH-CH520 — أحسن قيمة تحت 500 ريال 🎧',
    product: {
      icon: '🎧', name: 'Sony WH-CH520', badge: 'الأفضل',
      features: [
        'خفيف جداً — مثالي للمواصلات',
        'بطارية 50 ساعة',
        '⭐ 4.5 من 3,200 تقييم حقيقي',
        'بلوتوث 5.2 — اتصال مستقر',
      ],
      price: '449 ريال', couponCode: 'FAHIM10',
      couponSaving: 'هتدفع 400 ريال بدل من 449 لو استخدمت الكود',
      availability: 'متاح — يوصلك في يومين',
    },
  },
  {
    flag: '🇦🇪', country: 'الإمارات',
    userMsg: 'أنا بلبس حجاب وأبغى عباية أنيقة لرمضان',
    botMsg: 'ما شاء الله! جبتلك أجمل عبايات رمضان المحتشمة 🕌✨',
    product: {
      icon: '🧕', name: 'عباية كريب رمضانية فاخرة', badge: 'الأكثر طلباً',
      features: [
        'قماش كريب فاخر — مريح ومحتشم',
        'تصميم أنيق مناسب للمناسبات',
        '⭐ 4.7 من 890 تقييم',
        'متوفرة بأحجام S → 3XL',
      ],
      price: '189 درهم', couponCode: 'FAHIM10',
      couponSaving: 'هتدفعي 170 درهم بدل من 189 لو استخدمتي الكود',
      availability: 'متاح — يوصلك قبل رمضان',
    },
  },
  {
    flag: '🇪🇬', country: 'مصر',
    userMsg: 'عايز ساعة كلاسيك للشغل — شياكة بسعر معقول',
    botMsg: 'لقيتلك الاختيار المثالي! Casio Edifice — تلبسها في أي مناسبة ⌚',
    product: {
      icon: '⌚', name: 'Casio Edifice EF-527', badge: 'قيمة ممتازة',
      features: [
        'تصميم كلاسيك أنيق للشغل',
        'مقاوم للماء حتى 50 متر',
        '⭐ 4.6 من 1,450 تقييم',
        'ضمان سنتين — متاح في القاهرة',
      ],
      price: '2,199 ج.م', couponCode: 'FAHIM10',
      couponSaving: 'هتدفع 1,979 ج.م بدل من 2,199 لو استخدمت الكود',
      availability: 'متاح — يوصلك في يوم واحد',
    },
  },
]

/* single conversation — remounts via key so animations reset cleanly */
function ConversationDisplay({ conv }) {
  const [phase, setPhase] = useState('user')

  useEffect(() => {
    const ts = []
    ts.push(setTimeout(() => setPhase('typing'), 1400))
    ts.push(setTimeout(() => setPhase('reply'), 3200))
    return () => ts.forEach(clearTimeout)
  }, [])

  return (
    <div className="space-y-3">
      <div style={{ animation: 'fadeInUp 0.4s ease both' }} className="flex justify-start">
        <div className="bg-[#DCF8C6] rounded-2xl rounded-tr-none px-4 py-3 text-sm font-medium shadow-sm max-w-xs leading-relaxed">
          {conv.userMsg}
        </div>
      </div>

      {phase === 'typing' && (
        <div style={{ animation: 'fadeInUp 0.3s ease both' }} className="flex items-end gap-2">
          <img src="/logo.png" alt="فاهم" className="w-7 h-7 rounded-full object-cover shrink-0 shadow-sm" />
          <div className="bg-white rounded-tl-none rounded-tr-xl rounded-b-xl px-4 py-3 shadow-sm inline-block">
            <div className="typing-dots"><div className="typing-dot"/><div className="typing-dot"/><div className="typing-dot"/></div>
          </div>
        </div>
      )}

      {phase === 'reply' && (
        <>
          <div style={{ animation: 'fadeInUp 0.4s ease both' }} className="flex items-end gap-2">
            <img src="/logo.png" alt="فاهم" className="w-7 h-7 rounded-full object-cover shrink-0 shadow-sm" />
            <div className="bg-white rounded-tl-none rounded-tr-xl rounded-b-xl px-4 py-3 text-sm shadow-sm max-w-[82%] leading-relaxed">
              {conv.botMsg}
            </div>
          </div>

          <div style={{ animation: 'fadeInUp 0.5s ease 0.15s both' }} className="mr-9 bg-white rounded-3xl shadow-xl border border-border overflow-hidden">
            <div className="text-white px-5 py-4" style={{ background: 'linear-gradient(to right, #162F66, #1e3f8a)' }}>
              <div className="text-xs mb-0.5" style={{ color: 'rgba(255,255,255,0.75)' }}>🎯 توصيتي ليك:</div>
              <div className="font-extrabold text-lg">{conv.product.icon} {conv.product.name}</div>
            </div>
            <div className="px-5 pt-4 pb-3 border-b border-border">
              <div className="text-sm font-bold mb-2">✅ ليه ده بالظبط؟</div>
              <ul className="space-y-1.5">
                {conv.product.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                    <span className="text-primary mt-0.5 shrink-0">•</span><span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="px-5 py-3 border-b border-border flex gap-6 flex-wrap">
              <div>
                <div className="text-[10px] text-muted-foreground mb-0.5">💰 السعر</div>
                <div className="text-xl font-extrabold">{conv.product.price}</div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground mb-0.5">📦 التوفر</div>
                <div className="text-xs font-bold text-emerald-600 mt-1">{conv.product.availability}</div>
              </div>
            </div>
            <div className="px-5 py-3 border-b border-border bg-amber-50">
              <div className="flex items-start gap-3">
                <span className="text-xl mt-0.5">🎁</span>
                <div>
                  <div className="text-[10px] text-muted-foreground mb-1.5">كود خصم حصري — خصم 10%</div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="bg-primary text-white font-bold text-sm px-3 py-0.5 rounded-lg tracking-widest" dir="ltr">{conv.product.couponCode}</span>
                  </div>
                  <div className="text-sm font-bold text-primary">{conv.product.couponSaving}</div>
                </div>
              </div>
            </div>
            <div className="px-5 py-4">
              <a href="#" onClick={e => e.preventDefault()}
                className="flex items-center justify-center gap-2 w-full text-white font-bold text-sm rounded-2xl py-3 shadow-md hover:opacity-90 transition-opacity"
                style={{ background: 'linear-gradient(to right, #FF6F00, #FF8F00)' }}>
                👉 اشتري من نون
              </a>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function LiveDemoSection() {
  const [idx, setIdx] = useState(0)

  /* auto-advance — resets whenever idx changes (manual or auto) */
  useEffect(() => {
    const id = setTimeout(() => setIdx(p => (p + 1) % CONVERSATIONS.length), 9500)
    return () => clearTimeout(id)
  }, [idx])

  const conv = CONVERSATIONS[idx]

  return (
    <section className="py-24 bg-secondary/20" dir="rtl">
      <div className="max-w-5xl mx-auto px-6">
        <div className="text-center mb-14">
          <h2 className="text-3xl md:text-4xl font-extrabold mb-4">الفرق بين اللي اشترى صح واللي ندم؟ <span className="italic">فاهم</span>.</h2>
          <p className="text-xl text-muted-foreground">
            فاهم اتدرب على <strong>10 مليون منتج</strong> من نون مع مراجعات المشترين الحقيقيين. النتيجة؟ توصية دقيقة زي دي:
          </p>
        </div>

        {/* Country tabs */}
        <div className="flex justify-center gap-3 mb-8 flex-wrap">
          {CONVERSATIONS.map((c, i) => (
            <button key={i} onClick={() => setIdx(i)}
              className={`px-5 py-2 rounded-full text-sm font-bold border transition-all cursor-pointer ${
                idx === i
                  ? 'bg-primary text-white border-primary shadow-md'
                  : 'bg-white text-muted-foreground border-border hover:border-primary/40'
              }`}>
              {c.flag} {c.country}
            </button>
          ))}
        </div>

        {/* Chat window */}
        <div className="max-w-xl mx-auto">
          <div className="text-white px-5 py-3 rounded-t-3xl flex items-center gap-3"
            style={{ background: 'linear-gradient(to right, #162F66, #1e3f8a)' }}>
            <img src="/logo.png" alt="فاهم" className="w-10 h-10 rounded-full object-cover shrink-0 shadow" />
            <div>
              <div className="font-bold text-sm">فاهم | Fahim</div>
              <div className="text-xs flex items-center gap-1" style={{ color: 'rgba(255,255,255,0.8)' }}>
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" /> متصل الآن
              </div>
            </div>
            <div className="mr-auto text-lg">{conv.flag}</div>
          </div>

          <div className="px-5 py-5 min-h-[220px]" style={{ backgroundImage: 'url(/whatsapp_bg.jpeg)', backgroundSize: 'cover', backgroundPosition: 'center' }}>
            <ConversationDisplay key={idx} conv={conv} />
          </div>

          <div className="bg-[#f0f2f5] px-3 py-3 rounded-b-3xl">
            <div className="bg-white rounded-full px-4 py-2.5 text-sm text-gray-400 text-right">
              اسأل فاهم عن أي منتج...
            </div>
          </div>
        </div>

        <div className="mt-6 text-center text-sm text-muted-foreground">
          فاهم اختار ده من بين <strong>10 مليون منتج</strong> بناءً على احتياجك — مش الإعلانات المدفوعة
        </div>
      </div>
    </section>
  )
}

/* ─────────────────────────────────────────────
   Main page
───────────────────────────────────────────── */
export default function HomePage() {
  return (
    <div className="min-h-screen bg-background font-sans text-foreground">

      {/* ── Navbar ── */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md border-b"
        style={{ backgroundColor: 'hsl(220 30% 97% / 0.92)' }}>
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="فاهم" className="h-14 w-14 rounded-xl object-cover shadow-sm" />
            <span className="font-bold text-2xl tracking-tight text-primary">فاهم</span>
            <span className="hidden sm:inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground bg-secondary/60 px-2 py-0.5 rounded-full mr-1">
              🇪🇬 🇸🇦 🇦🇪
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden md:block text-base text-muted-foreground font-medium">متاح مجاناً الآن</span>
            <Link to="/chat">
              <button className="rounded-full px-5 py-2 bg-primary text-white shadow hover:shadow-lg transition-all font-bold text-sm cursor-pointer border-0 hover:-translate-y-0.5">
                جرب فاهم مجاناً ✨
              </button>
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Trust marquee ── */}
      <div className="pt-20">
        <TrustMarquee />
      </div>

      {/* ── Hero ── */}
      <section className="pt-20 pb-20 px-6 md:pt-28 md:pb-32 overflow-hidden relative">
        {/* Background gradient */}
        <div className="absolute inset-0 -z-10"
          style={{ background: 'radial-gradient(ellipse 80% 60% at 70% 0%, hsl(220 65% 22% / 0.07) 0%, transparent 70%), radial-gradient(ellipse 60% 40% at 0% 100%, hsl(43 88% 52% / 0.05) 0%, transparent 70%)' }} />

        {/* Neural brain background */}
        <NeuralBrain style={{ opacity: 0.75, zIndex: 0 }} />

        <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-16 items-center relative z-10" dir="rtl">

          {/* Left: copy */}
          <div className="max-w-xl fade-in-up">
            <h1 className="text-4xl lg:text-5xl font-extrabold leading-[1.15] mb-5 text-foreground">
              فاهم مش بيبيعلك،<br />
              بيساعدك تشتري صح.
            </h1>

            <div className="mb-4" />

            <p className="text-lg text-muted-foreground mb-8 leading-relaxed font-medium">
              محتار تشتري إيه؟ فاهم بيسألك كام سؤال، بيفهم احتياجاتك،<br />وبيرشحلك أفضل المنتجات على نون مع كوبون خصم حصري في ثواني.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-3 mb-10">
              <Link to="/chat">
                <button className="rounded-full px-8 h-13 py-3.5 text-base w-full sm:w-auto shadow-lg hover:shadow-xl transition-all font-bold bg-primary text-white border-0 cursor-pointer hover:-translate-y-0.5 text-lg">
                  ابدأ المحادثة مع فاهم 🚀
                </button>
              </Link>
              <button className="rounded-full px-8 py-3.5 text-base w-full sm:w-auto font-bold bg-white hover:bg-gray-50 border border-gray-200 cursor-pointer transition-colors text-foreground text-lg">
                إزاي بيشتغل؟
              </button>
            </div>

            {/* mini social proof */}
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <div className="flex -space-x-2 rtl:space-x-reverse">
                {['🧑‍💼','👩','🧕','👨‍💻'].map((e,i) => (
                  <div key={i} className="w-8 h-8 rounded-full bg-secondary border-2 border-white flex items-center justify-center text-base shadow-sm">{e}</div>
                ))}
              </div>
              <span className="font-semibold"><strong className="text-foreground">+5,000</strong> مستخدم من مصر والسعودية والإمارات</span>
            </div>
          </div>

          {/* Right: animated phone */}
          <div className="relative fade-in-left flex justify-center lg:-translate-x-[75px]">
            {/* glow */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[110%] h-[110%] blur-3xl rounded-full -z-10"
              style={{ background: 'radial-gradient(circle, hsl(220 65% 22% / 0.12) 0%, hsl(43 88% 52% / 0.08) 60%, transparent 100%)' }} />
            <AnimatedPhone />
          </div>
        </div>
      </section>

      {/* ── Stats ── */}
      <section className="py-12 bg-white border-y border-border" dir="rtl">
        <div className="max-w-5xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { value: '10M+', label: 'منتج محلّل على نون' },
              { value: '٣ دول', label: 'مصر · السعودية · الإمارات' },
              { value: '٪10', label: 'خصم حصري مع كل توصية' },
              { value: '< 3ث', label: 'متوسط وقت الرد' },
            ].map((s, i) => (
              <div key={i}>
                <div className="text-3xl md:text-4xl font-extrabold mb-1 stat-shimmer">{s.value}</div>
                <div className="text-sm text-muted-foreground font-medium">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="py-24 bg-background relative overflow-hidden" dir="rtl">
        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-extrabold mb-4">ليه تسأل فاهم؟</h2>
            <p className="text-xl text-muted-foreground">عشان التسوق مفروض يكون ممتع، مش متعب.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8 items-center">
            {[
              {
                icon: '🧠', title: 'اتدرب على 10 مليون منتج',
                text: <>فاهم اتدرب على <strong>10 مليون منتج</strong> من نون، مع مراجعات المشترين الحقيقيين اللي جربوا المنتجات بعد الشراء — مش المواصفات من الشركة بس.</>,
              },
              {
                icon: '⚠️', title: 'بيتجاهل الإعلانات المدفوعة',
                text: <>أول <strong>50–100 منتج بيظهروا على نون هم إعلانات مدفوعة</strong> — الشركة دفعت عشان تظهرهم في أول. فاهم بيتجاهلهم ويدور على الأفضل لاستخدامك انت.</>,
              },
              {
                icon: '🎁', title: 'كوبون خصم حصري مع كل توصية',
                text: <>مع كل توصية، فاهم بيديك كود خصم حصري بيوصل لـ <strong>10% من سعر المنتج</strong> — على المنتج اللي اخترناه ليك بالظبط.</>,
              },
            ].map((item, i) => (
              <div key={i} className={`bg-white rounded-3xl border text-center hover:shadow-md hover:-translate-y-1 transition-all ${
                i === 1
                  ? 'p-10 border-primary/30 shadow-lg shadow-primary/8 md:scale-105'
                  : 'p-8 border-border shadow-sm'
              }`}>
                <div className={`rounded-2xl flex items-center justify-center mx-auto mb-6 ${i === 1 ? 'w-20 h-20 text-4xl' : 'w-16 h-16 text-3xl'}`}
                  style={{ backgroundColor: 'hsl(220 65% 22% / 0.08)' }}>
                  {item.icon}
                </div>
                <h3 className={`font-bold mb-3 ${i === 1 ? 'text-2xl' : 'text-xl'}`}>{item.title}</h3>
                <p className={`leading-relaxed ${i === 1 ? 'text-base text-foreground/80' : 'text-muted-foreground'}`}>{item.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Live Demo ── */}
      <LiveDemoSection />

      {/* ── Categories ── */}
      <section className="py-24 bg-white" dir="rtl">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-extrabold mb-4">تقدر تسأل فاهم عن إيه؟</h2>
            <p className="text-xl text-muted-foreground">من الأجهزة للموضة — فاهم بيلاقيلك الأنسب في ثواني.</p>
          </div>
          {[
            { label: 'أجهزة وتكنولوجيا', cats: ['📱 موبايلات', '💻 لابتوبات', '❄️ تكييفات', '📺 شاشات', '🎧 سماعات', '📷 كاميرات', '🎮 أجهزة ألعاب', '⌚ ساعات ذكية'] },
            { label: 'موضة واكسسوارات', cats: ['🛍️ أزياء رمضان', '🧕 موضة محتشمة', '👗 عبايات وخمارات', '🕶️ نظارات شمسية', '⌚ ساعات كلاسيك', '📿 ساعات التسبيح', '👟 أحذية', '👜 شنط وحقائب'] },
          ].map((group, gi) => (
            <div key={gi} className="mb-8">
              <div className="text-sm font-bold text-muted-foreground mb-3 flex items-center gap-2">
                <span className="w-6 h-px bg-border inline-block"></span>
                {group.label}
                <span className="flex-1 h-px bg-border inline-block"></span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {group.cats.map((cat, i) => (
                  <div key={i} className="bg-secondary/30 p-5 rounded-2xl border border-border text-center font-bold text-base hover:-translate-y-1 hover:shadow-md hover:bg-secondary/60 transition-all cursor-pointer">
                    {cat}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Use Cases ── */}
      <section className="py-24 bg-primary text-primary-foreground relative overflow-hidden" dir="rtl">
        <div className="absolute inset-0 opacity-5"
          style={{ backgroundImage: 'radial-gradient(#ffffff 1.5px, transparent 1.5px)', backgroundSize: '28px 28px' }} />
        <div className="max-w-6xl mx-auto px-6 relative z-10">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 rounded-full mb-5 px-4 py-1.5 text-sm font-semibold"
              style={{ backgroundColor: 'rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.9)' }}>
              ⚡ في أقل من 3 ثواني
            </div>
            <h2 className="text-3xl md:text-4xl font-extrabold mb-4">فاهم مش بس للأجهزة</h2>
            <p className="text-xl" style={{ color: 'rgba(255,255,255,0.8)' }}>جرب تسأله عن الموضة، الإكسسوارات، أي حاجة — وشوف بإيدك</p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                icon: '🧕', title: 'موضة رمضان والموضة المحتشمة',
                text: 'قوله "عايزة عباية أنيقة لرمضان" أو "محتاجة ملابس تغطي الذراعين" — هيجبلك اختيارات مناسبة.',
                tags: ['عبايات', 'خمارات وحجاب', 'موضة رمضان', 'تغطية كاملة'],
              },
              {
                icon: '🕶️', title: 'نظارات شمسية للشاطئ',
                text: 'قوله "عايز نظارة شمسية" — في ثواني هيجبلك أحسن حماية UV بسعر يناسب ميزانيتك.',
                tags: ['UV Protection', 'شاطئ وبحر', 'رجالي ونسائي', 'ماركات معتمدة'],
              },
              {
                icon: '⌚', title: 'ساعات كلاسيك وتسبيح رمضان',
                text: '"عايز ساعة للشغل" أو "ساعة تسبيح" — فاهم هيجبلك الأنسب من ملايين المنتجات.',
                tags: ['ساعات كلاسيك', 'للشغل والمناسبات', 'تسبيح رقمي', 'رمضان'],
              },
            ].map((card, i) => (
              <div key={i} className="rounded-3xl p-6 border transition-all hover:-translate-y-1"
                style={{ backgroundColor: 'rgba(255,255,255,0.1)', borderColor: 'rgba(255,255,255,0.2)' }}
                onMouseEnter={e => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.16)'}
                onMouseLeave={e => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)'}>
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl mb-5"
                  style={{ backgroundColor: 'hsl(43 88% 52% / 0.2)' }}>{card.icon}</div>
                <h3 className="text-xl font-extrabold mb-3">{card.title}</h3>
                <p className="text-sm leading-relaxed mb-4" style={{ color: 'rgba(255,255,255,0.8)' }}>{card.text}</p>
                <div className="flex flex-wrap gap-2">
                  {card.tags.map(tag => (
                    <span key={tag} className="text-xs font-semibold px-3 py-1 rounded-full"
                      style={{ backgroundColor: 'rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.9)' }}>{tag}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="text-center mt-10">
            <Link to="/chat">
              <button className="rounded-full px-8 py-4 text-lg bg-white text-primary hover:bg-gray-50 font-bold shadow-xl cursor-pointer border-0 transition-all hover:-translate-y-0.5">
                جرب فاهم دلوقتي — مجاناً 🎉
              </button>
            </Link>
          </div>
        </div>
      </section>

      {/* ── Testimonials ── */}
      <section className="py-24 bg-secondary/20" dir="rtl">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-extrabold mb-3">آراء اللي جربوا فاهم</h2>
            <p className="text-muted-foreground text-lg">من مصر والسعودية والإمارات</p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { text: 'أول مرة أشتري تكييف ومابقاش تايه. فاهم سألني على مساحة الأوضة وجابلي الموديل الصح بالظبط.', author: 'أحمد م.', country: '🇪🇬 القاهرة' },
              { text: 'وفّر عليّ أكثر من 200 ريال بكوبون الخصم! كنت أبحث عن لابتوب للدراسة وجاء بأفضل توصية.', author: 'فاطمة الغامدي', country: '🇸🇦 الرياض' },
              { text: 'كنت محتار بين جهازين، فاهم قارن بسرعة وعرفني الأنسب لاحتياجاتي وبميزانيتي بالضبط.', author: 'خالد الهاشمي', country: '🇦🇪 دبي' },
            ].map((t, i) => (
              <div key={i} className="bg-white p-8 rounded-3xl border border-border shadow-sm hover:shadow-md transition-shadow">
                <div className="flex gap-1 mb-4 text-accent text-lg">{'★'.repeat(5)}</div>
                <p className="text-base leading-relaxed mb-6 font-medium">"{t.text}"</p>
                <div className="flex items-center justify-between">
                  <div className="text-foreground font-bold">{t.author}</div>
                  <div className="text-sm text-muted-foreground font-semibold">{t.country}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section className="py-24 bg-background border-t border-border" dir="rtl">
        <div className="max-w-3xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-extrabold">الأسئلة الشائعة</h2>
          </div>
          <div className="space-y-4">
            {[
              {
                q: 'هل فاهم متاح في مصر والسعودية والإمارات؟',
                a: 'أيوه! فاهم بيشتغل مع نون في الثلاث دول. الأسعار والكوبونات بتتغير تلقائياً حسب بلدك.',
              },
              {
                q: 'هل فاهم خدمة مجانية؟',
                a: 'أيوه، تقدر تستخدم فاهم مجاناً عشان تلاقي المنتجات اللي بتدور عليها وتاخد كوبون الخصم.',
              },
              {
                q: 'إزاي فاهم بيجيب المنتجات؟',
                a: (
                  <div className="space-y-4 text-sm leading-relaxed">
                    <div className="flex gap-3 items-start">
                      <span className="text-xl shrink-0">🧠</span>
                      <p>فاهم اتدرب على <strong className="text-foreground">10 مليون منتج</strong> من نون، مع مراجعات المشترين الحقيقيين اللي جربوا المنتجات بعد الشراء — مش المواصفات من الشركة بس.</p>
                    </div>
                    <div className="flex gap-3 items-start">
                      <span className="text-xl shrink-0">⚠️</span>
                      <p>مشكلة التسوق العادي: أول <strong className="text-foreground">50–100 منتج بيظهروا على نون هم إعلانات مدفوعة</strong> — يعني الشركة دفعت عشان تظهر أول. ده مش بالضرورة يعني إنهم الأنسب لاحتياجك. فاهم بيتجاهل الإعلانات ويدور على الأفضل لاستخدامك الحقيقي.</p>
                    </div>
                    <div className="flex gap-3 items-start">
                      <span className="text-xl shrink-0">🎁</span>
                      <p>مع كل توصية، فاهم بيديك كود خصم حصري بيوصل لـ <strong className="text-foreground">10% من سعر المنتج</strong> — على المنتج اللي اخترناه ليك بالظبط.</p>
                    </div>
                  </div>
                ),
              },
              {
                q: 'هل أكواد الخصم دايماً شغالة؟',
                a: 'بنسبة كبيرة جداً! فاهم بيحاول دايماً يديك أحدث وأفضل أكواد الخصم المتاحة.',
              },
            ].map((item, i) => (
              <div key={i} className="bg-white p-6 rounded-2xl border border-border hover:shadow-sm transition-shadow">
                <h3 className="text-lg font-bold mb-2">{item.q}</h3>
                <div className="text-muted-foreground leading-relaxed">{item.a}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="py-24 bg-primary text-primary-foreground relative overflow-hidden" dir="rtl">
        <div className="absolute inset-0 opacity-10"
          style={{ backgroundImage: 'radial-gradient(#ffffff 2px, transparent 2px)', backgroundSize: '30px 30px' }} />
        <div className="absolute top-0 left-0 w-96 h-96 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2"
          style={{ backgroundColor: 'hsl(43 88% 52% / 0.2)' }} />
        <div className="max-w-4xl mx-auto px-6 text-center relative z-10">
          <div className="text-5xl mb-6">🛍️</div>
          <h2 className="text-4xl md:text-6xl font-extrabold mb-6 leading-tight">جاهز تشتري بذكاء؟</h2>
          <p className="text-xl mb-3" style={{ color: 'rgba(255,255,255,0.85)' }}>
            جرب فاهم دلوقتي مجاناً وشوف إزاي ممكن يوفرلك وقت وفلوس.
          </p>
          <p className="text-sm mb-10 font-semibold" style={{ color: 'rgba(255,255,255,0.6)' }}>
            متاح في 🇪🇬 مصر &nbsp;·&nbsp; 🇸🇦 السعودية &nbsp;·&nbsp; 🇦🇪 الإمارات
          </p>
          <Link to="/chat">
            <button className="rounded-full px-10 py-5 text-xl shadow-2xl hover:scale-105 transition-transform bg-white text-primary hover:bg-gray-50 font-bold border-0 cursor-pointer">
              كلم فاهم دلوقتي ✨
            </button>
          </Link>
        </div>
      </section>

      {/* ── Floating chat widget ── */}
      <FloatingChat />

      {/* ── Footer ── */}
      <footer className="bg-background py-12 border-t border-border text-center" dir="rtl">
        <div className="max-w-7xl mx-auto px-6 flex flex-col items-center">
          <img src="/logo.png" alt="فاهم" className="w-16 h-16 rounded-2xl object-cover mb-4 shadow-md" />
          <div className="font-bold text-2xl mb-1 text-foreground">فاهم</div>
          <p className="text-muted-foreground mb-2">المساعد الذكي الأول للتسوق على نون</p>
          <p className="text-sm text-muted-foreground mb-6">🇪🇬 مصر &nbsp;·&nbsp; 🇸🇦 السعودية &nbsp;·&nbsp; 🇦🇪 الإمارات</p>
          <div className="text-sm text-muted-foreground/60">
            © {new Date().getFullYear()} فاهم. جميع الحقوق محفوظة.
          </div>
        </div>
      </footer>
    </div>
  )
}
