import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

// iOS home-screen standalone mode has a long history of `100dvh` not
// actually equalling the real screen height (it can settle short, leaving a
// black gap top and/or bottom) - a bug that does not show up in a regular
// Safari tab, only once "installed". Measuring the real viewport in JS and
// exposing it as a custom property sidesteps every CSS viewport-unit quirk
// across dvh/svh/lvh and browser/mode combinations.
function setAppHeight() {
  const h = (window.visualViewport && window.visualViewport.height) || window.innerHeight
  document.documentElement.style.setProperty('--app-height', h + 'px')
}
setAppHeight()
window.addEventListener('resize', setAppHeight)
window.addEventListener('orientationchange', setAppHeight)
if (window.visualViewport) window.visualViewport.addEventListener('resize', setAppHeight)

createApp(App).mount('#app')
