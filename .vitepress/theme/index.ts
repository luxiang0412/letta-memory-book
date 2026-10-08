// Default theme + click-to-zoom for every image in the article body.
import DefaultTheme from 'vitepress/theme'
import mediumZoom from 'medium-zoom'
import { nextTick, onMounted, watch } from 'vue'
import { useRoute } from 'vitepress'
import './custom.css'

export default {
  extends: DefaultTheme,
  setup() {
    const route = useRoute()
    const init = () => mediumZoom('.vp-doc img', { background: 'var(--vp-c-bg)', margin: 24 })
    onMounted(init)
    // VitePress is an SPA: re-attach after each client-side navigation.
    watch(() => route.path, () => nextTick(init))
  },
}
