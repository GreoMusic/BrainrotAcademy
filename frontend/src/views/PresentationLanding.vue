<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import mistralIcon from '../assets/mistral-icon.png'
import mistralLockup from '../assets/mistral-lockup-gradient.png'
import voxtralModel from '../assets/voxtral-model.png'

const showcase = ref(null)
let observer = null

function tilt(event) {
  if (!showcase.value || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const rect = showcase.value.getBoundingClientRect()
  const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
  const y = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))
  showcase.value.style.setProperty('--pointer-x', `${x * 100}%`)
  showcase.value.style.setProperty('--pointer-y', `${y * 100}%`)
  showcase.value.style.setProperty('--rotate-y', `${(x - 0.5) * 5}deg`)
  showcase.value.style.setProperty('--rotate-x', `${(0.5 - y) * 4}deg`)
}

function resetTilt() {
  if (!showcase.value) return
  showcase.value.style.setProperty('--rotate-y', '0deg')
  showcase.value.style.setProperty('--rotate-x', '0deg')
}

onMounted(() => {
  document.body.classList.add('presentation-mode')
  observer = new IntersectionObserver(
    (entries) => entries.forEach((entry) => entry.isIntersecting && entry.target.classList.add('visible')),
    { threshold: 0.2 },
  )
  document.querySelectorAll('.presentation-page .reveal').forEach((node) => observer.observe(node))
})

onBeforeUnmount(() => {
  document.body.classList.remove('presentation-mode')
  observer?.disconnect()
})
</script>

<template>
  <main class="presentation-page">
    <div class="presentation-grid" aria-hidden="true" />
    <div class="presentation-grain" aria-hidden="true" />

    <nav class="presentation-nav">
      <a class="presentation-brand" href="/landingpage">Brainrot Academy</a>
      <div class="powered"><span>Powered by</span><img :src="mistralLockup" alt="Mistral" /></div>
    </nav>

    <section class="presentation-section hero-section">
      <div class="hero-orbit" aria-hidden="true"><span /><span /><span /></div>
      <div class="hero-content reveal visible">
        <p class="eyebrow">The anti-doomscroll learning loop</p>
        <h1><span>What if learning</span><em>could be dynamic?</em></h1>
        <p class="hero-sub">
          Brainrot Academy turns attention into a reward loop—learn something,
          prove you understand it, then earn the scroll.
        </p>
        <a class="hero-link" href="#experience">See how it works <span>↓</span></a>
      </div>
    </section>

    <section id="experience" class="presentation-section experience-section">
      <div class="section-heading reveal">
        <p class="eyebrow">A learning product that speaks internet</p>
        <h2><span>You don’t get the feed.</span><span>You earn it.</span></h2>
      </div>

      <div
        ref="showcase"
        class="showcase reveal"
        @pointermove="tilt"
        @pointerleave="resetTilt"
      >
        <div class="showcase-sheen" aria-hidden="true" />
        <div class="showcase-word" aria-hidden="true">ACADEMY</div>

        <div class="showcase-copy">
          <span class="showcase-index">01 — THE LOOP</span>
          <h3>Learn.<br />Explain.<br /><b>Unlock.</b></h3>
          <p>Dynamic lessons, Voxtral voice coaching, and intentional friction—all in one continuous feed.</p>
        </div>

        <div class="demo-phone-wrap">
          <div class="demo-phone">
            <div class="demo-island" />
            <div class="demo-screen">
              <span class="demo-pill">LEARNING ROUND</span>
              <div class="demo-tabs"><i class="on" /><i /><i /></div>
              <div class="demo-card">
                <small>FLASHCARD</small>
                <strong>Why does spaced repetition work?</strong>
                <p>Your brain remembers what it has to retrieve.</p>
              </div>
              <div class="demo-coach">
                <div class="coach-avatar"><span /></div>
                <div><small>LIVE COACH</small><p>Explain it back in your own words.</p></div>
              </div>
              <button>Hold to answer</button>
            </div>
          </div>
          <div class="floating-badge voice-badge"><i><img :src="voxtralModel" alt="Voxtral" /></i><span><b>Voxtral voice</b><small>Live coaching</small></span></div>
          <div class="floating-badge content-badge"><i><img :src="mistralIcon" alt="Mistral" /></i><span><b>Generated with Mistral</b><small>Dynamic learning content</small></span></div>
          <div class="floating-badge scroll-badge"><i>✓</i><span><b>Scroll unlocked</b><small>Understanding verified</small></span></div>
        </div>

        <div class="showcase-metric">
          <span>06</span><small>earned<br />scrolls</small>
        </div>
      </div>
    </section>

  </main>
</template>

<style scoped>
:global(body.presentation-mode) { overflow-y: auto; overflow-x: hidden; background: #f5f2ec; }
:global(body.presentation-mode #app) { height: auto; min-height: 100%; }
.presentation-page {
  --warm: #d75a24; --orange: #f07a2c; --cream: #f5f2ec; --charcoal: #171513;
  position: relative; min-height: 100vh; overflow: hidden; color: var(--charcoal);
  background: var(--cream); user-select: none;
}
.presentation-grid {
  position: fixed; inset: 0; z-index: 0; pointer-events: none; opacity: 0.36;
  background-image: linear-gradient(rgba(23,21,19,.045) 1px, transparent 1px), linear-gradient(90deg, rgba(23,21,19,.045) 1px, transparent 1px);
  background-size: 64px 64px;
  -webkit-mask-image: radial-gradient(ellipse at center, #000, transparent 72%); mask-image: radial-gradient(ellipse at center, #000, transparent 72%);
}
.presentation-grain {
  position: fixed; inset: 0; z-index: 80; pointer-events: none; opacity: .035; mix-blend-mode: multiply;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}
.presentation-nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 70; height: 74px; padding: 0 clamp(24px, 5vw, 76px);
  display: flex; align-items: center; justify-content: space-between;
  background: linear-gradient(to bottom, rgba(245,242,236,.92), rgba(245,242,236,0));
}
.presentation-brand { color: #b94b21; font-family: "Grand Hotel", cursive; font-size: 28px; text-decoration: none; }
.powered { height: 28px; display: flex; align-items: center; gap: 8px; color: #6b625c; font-size: 9px; font-weight: 750; line-height: 1; letter-spacing: .1em; text-transform: uppercase; }
.powered span { display: block; transform: translateY(1px); }
.powered img { width: 72px; height: auto; flex: none; display: block; object-fit: contain; }
.presentation-section { position: relative; z-index: 1; width: 100%; min-height: 100vh; padding: 110px clamp(24px, 6vw, 96px); }
.hero-section { display: grid; place-items: center; text-align: center; }
.hero-content { position: relative; z-index: 2; max-width: 1040px; }
.eyebrow { margin-bottom: 22px; color: #a94a25; font-size: 11px; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; }
.hero-content h1 { font-size: clamp(54px, 7.4vw, 108px); line-height: .94; letter-spacing: -.055em; font-weight: 680; }
.hero-content h1 span, .hero-content h1 em { display: block; white-space: nowrap; }
.hero-content h1 em { color: var(--warm); font-style: normal; }
.hero-sub { max-width: 640px; margin: 34px auto 0; color: #6d6761; font-size: clamp(16px, 1.6vw, 21px); line-height: 1.65; }
.hero-link { display: inline-flex; align-items: center; gap: 12px; margin-top: 38px; color: var(--charcoal); font-size: 13px; font-weight: 760; text-decoration: none; }
.hero-link span { width: 30px; height: 30px; display: grid; place-items: center; border: 1px solid #cfc8bf; border-radius: 50%; }
.hero-orbit { position: absolute; top: 50%; left: 50%; width: min(82vw, 980px); aspect-ratio: 1.5; transform: translate(-50%,-50%); opacity: .8; }
.hero-orbit::before { content: ''; position: absolute; inset: 8%; border: 1px solid rgba(215,90,36,.12); border-radius: 50%; transform: rotate(-9deg); }
.hero-orbit span { position: absolute; border-radius: 50%; filter: blur(48px); animation: orbit-pulse 7s ease-in-out infinite; }
.hero-orbit span:nth-child(1) { width: 34%; height: 45%; top: 5%; left: 5%; background: rgba(255,194,112,.23); }
.hero-orbit span:nth-child(2) { width: 29%; height: 40%; right: 7%; bottom: 3%; background: rgba(215,90,36,.16); animation-delay: -2s; }
.hero-orbit span:nth-child(3) { width: 20%; height: 28%; left: 42%; bottom: 5%; background: rgba(255,222,170,.35); animation-delay: -4s; }
@keyframes orbit-pulse { 50% { transform: scale(1.14) translateY(-12px); opacity: .68; } }
.experience-section { padding-top: 120px; }
.section-heading { max-width: 900px; margin-bottom: 58px; }
.section-heading h2 { font-size: clamp(43px, 5.2vw, 74px); line-height: .98; letter-spacing: -.055em; }
.section-heading h2 > span { display: block; white-space: nowrap; }
.showcase {
  --rotate-x: 0deg; --rotate-y: 0deg; --pointer-x: 50%; --pointer-y: 50%;
  position: relative; width: 100%; min-height: min(720px, 78vh); padding: clamp(30px, 5vw, 72px);
  display: grid; grid-template-columns: 1fr minmax(300px, .9fr) .5fr; align-items: center; gap: 30px;
  overflow: hidden; border: 1px solid rgba(255,255,255,.08); border-radius: 42px;
  color: #fff; background: linear-gradient(145deg, #402118, #181311 62%, #100e0d);
  box-shadow: 0 60px 120px -50px rgba(41,24,17,.68), inset 0 1px rgba(255,255,255,.14);
  transform: perspective(1500px) rotateX(var(--rotate-x)) rotateY(var(--rotate-y));
  transition: transform .7s cubic-bezier(.22,1,.36,1);
}
.showcase-sheen { position: absolute; inset: 0; background: radial-gradient(700px circle at var(--pointer-x) var(--pointer-y), rgba(255,255,255,.1), transparent 42%); pointer-events: none; }
.showcase-word { position: absolute; right: -2%; top: 4%; color: rgba(255,255,255,.025); font-size: clamp(100px, 18vw, 270px); font-weight: 900; letter-spacing: -.08em; }
.showcase-copy, .demo-phone-wrap, .showcase-metric { position: relative; z-index: 2; }
.showcase-index { color: #e99068; font-size: 10px; font-weight: 800; letter-spacing: .15em; }
.showcase-copy h3 { margin-top: 20px; font-size: clamp(46px, 5vw, 76px); line-height: .89; letter-spacing: -.055em; }
.showcase-copy h3 b { color: #f19162; }
.showcase-copy p { max-width: 350px; margin-top: 28px; color: rgba(255,255,255,.58); font-size: 14px; line-height: 1.65; }
.demo-phone-wrap { height: 560px; display: grid; place-items: center; perspective: 1000px; }
.demo-phone { position: relative; width: 270px; height: 550px; padding: 9px; border-radius: 48px; background: #090909; box-shadow: inset 0 0 0 2px #4a4542, inset 0 0 0 7px #000, 0 35px 70px rgba(0,0,0,.65); transform: rotateY(-4deg); }
.demo-island { position: absolute; top: 16px; left: 50%; z-index: 5; width: 88px; height: 22px; transform: translateX(-50%); border-radius: 99px; background: #000; }
.demo-screen { height: 100%; padding: 54px 19px 20px; overflow: hidden; border-radius: 39px; color: #24201d; background: #fff; }
.demo-pill { display: inline-flex; padding: 5px 9px; border-radius: 99px; color: #fff; background: var(--warm); font-size: 8px; font-weight: 800; letter-spacing: .06em; }
.demo-tabs { display: flex; gap: 5px; margin: 17px 0; }.demo-tabs i { flex: 1; height: 3px; border-radius: 4px; background: #ece8e4; }.demo-tabs i.on { background: var(--orange); }
.demo-card { height: 188px; padding: 21px; display: flex; flex-direction: column; justify-content: center; border: 1px solid #f2e5dc; border-radius: 20px; background: linear-gradient(155deg,#fff8f3,#fff1ea); }
.demo-card small, .demo-coach small { color: var(--warm); font-size: 8px; font-weight: 800; letter-spacing: .08em; }.demo-card strong { margin: 9px 0; font-size: 18px; line-height: 1.1; }.demo-card p { color: #777; font-size: 10px; line-height: 1.45; }
.demo-coach { margin: 15px 0; padding: 12px; display: flex; align-items: center; gap: 10px; border: 1px solid #eee8e4; border-radius: 15px; }.demo-coach p { margin-top: 3px; font-size: 9px; }.coach-avatar { width: 32px; height: 32px; flex: none; display: grid; place-items: center; border-radius: 50%; background: #fff0e7; }.coach-avatar span { width: 12px; height: 12px; border: 2px solid var(--warm); border-radius: 50%; }
.demo-screen button { width: 100%; padding: 11px; border-radius: 99px; color: #fff; background: var(--warm); font-size: 10px; font-weight: 750; }
.floating-badge { position: absolute; z-index: 8; min-width: 174px; padding: 12px 14px; display: flex; align-items: center; gap: 10px; border: 1px solid rgba(255,255,255,.14); border-radius: 15px; color: #fff; background: rgba(255,255,255,.08); -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px); box-shadow: 0 20px 45px rgba(0,0,0,.35); animation: badge-float 4.6s ease-in-out infinite; }
.floating-badge i { width: 31px; height: 31px; display: grid; place-items: center; overflow: hidden; border-radius: 9px; color: #ffd2bd; background: rgba(240,122,44,.17); font-style: normal; }
.floating-badge i img { width: 100%; height: 100%; object-fit: cover; }
.floating-badge span,.floating-badge b,.floating-badge small { display: block; }
.floating-badge b { font-size: 11px; }
.floating-badge small { margin-top: 2px; color: rgba(255,255,255,.48); font-size: 8.5px; }
.voice-badge { top: 52px; left: -72px; }
.content-badge { top: 158px; right: -88px; animation-delay: -1s; }
.content-badge i { color: #211510; background: #f5f2ec; font-size: 11px; font-weight: 900; }
.scroll-badge { right: -82px; bottom: 64px; animation-delay: -2s; }
@keyframes badge-float { 50% { transform: translateY(-10px); } }
.showcase-metric { display: flex; align-items: end; gap: 9px; justify-self: end; }.showcase-metric span { color: #f2a17a; font-size: 64px; font-weight: 800; line-height: .8; letter-spacing: -.06em; }.showcase-metric small { color: rgba(255,255,255,.45); font-size: 9px; font-weight: 700; line-height: 1.35; letter-spacing: .1em; text-transform: uppercase; }
.reveal { opacity: 0; transform: translateY(42px); transition: opacity .9s ease, transform .9s cubic-bezier(.22,1,.36,1); }.reveal.visible { opacity: 1; transform: translateY(0); }
@media (max-width: 900px) {
  .presentation-section { padding-left: 22px; padding-right: 22px; }
  .showcase { grid-template-columns: 1fr; padding: 34px 22px; text-align: center; }
  .showcase-copy p { margin-left: auto; margin-right: auto; }.showcase-metric { display: none; }.demo-phone-wrap { height: 520px; }.voice-badge { left: -5px; }.content-badge { right: -8px; }.scroll-badge { right: -8px; }
}
@media (max-width: 560px) {
  .presentation-nav { height: 62px; padding: 0 18px; }.presentation-brand { font-size: 24px; }.powered { font-size: 8px; }
  .presentation-section { min-height: 100svh; padding-top: 90px; padding-bottom: 70px; }.hero-content h1 { font-size: clamp(42px, 13vw, 52px); }.hero-sub { font-size: 15px; }
  .experience-section .section-heading { text-align: center; }.section-heading h2 { font-size: 42px; }.showcase { border-radius: 28px; }.showcase-copy h3 { font-size: 49px; }
  .demo-phone-wrap { height: 470px; transform: scale(.88); margin: -26px 0; }.floating-badge { min-width: 152px; }
}
@media (prefers-reduced-motion: reduce) { .hero-orbit span,.floating-badge { animation: none; }.reveal { opacity: 1; transform: none; transition: none; }.showcase { transform: none !important; } }
</style>
