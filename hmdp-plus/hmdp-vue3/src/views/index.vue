<script setup>
import {
  indexQueryTypes,
  indexQueryHotBlogsScroll,
  indexAddLike,
  indexQueryBlogById
} from '@/api/user'
import { ref } from 'vue'
import router from '@/router'
import FootBar from '@/components/FootBar.vue'
import CityPicker from '@/components/CityPicker.vue'
import { useTravelStore } from '@/stores/modules/travel'
import { User, MagicStick, ArrowRight } from '@element-plus/icons-vue'
const isReachBottom = ref(false)
const types = ref([])
const blogs = ref([])
const current = ref(1)
const travel = useTravelStore()
const cityOpen = ref(false)
const searchKeyword = ref('')
const searchPlacesInCity = () => {
  const keyword = searchKeyword.value.trim()
  if (!keyword) return
  travel.draft = `请在${travel.selectedCity || '我准备去的城市'}搜索${keyword}，先核对城市再推荐。`
  router.push('/travel')
}

// 获取首页商品列表数据
const queryTypes = async () => {
  try {
    console.log('获取首页商品列表数据')
    const response = await indexQueryTypes()
    console.log('获取首页商品列表数据:', response.data)
    // const data = await response.json()
    types.value = response.data
  } catch (error) {
    console.log('获取首页商品列表数据失败:', error)
  }
}
queryTypes()
// 获取首页博客数据
const queryHotBlogsScroll = async () => {
  try {
    console.log('获取首页博客数据')
    const { data } = await indexQueryHotBlogsScroll()
    console.log('获取首页博客数据:', data)
    data.forEach((b) => {
      if (b && b.images) {
        b.img = b.images.split(',')[0]
      } else {
        b.img = ''
      }
    })
    blogs.value = blogs.value.concat(data)
  } catch (error) {
    console.log('获取首页博客数据失败:', error)
  }
}
queryHotBlogsScroll()
// 添加点赞
const addLike = async (blog) => {
  try {
    await indexAddLike(blog.id)
    await queryBlogById(blog)
  } catch (error) {
    console.log(error)
  }
}
// 根据id查询博客
const queryBlogById = async (blog) => {
  try {
    const { data } = await indexQueryBlogById(blog.id)
    blog.liked = data.liked
    blog.isLike = data.isLike
  } catch (error) {
    console.log(error)
    blog.liked++
  }
}
// 滚动到底部加载更多数据
const onScroll = (e) => {
  let scrollTop = e.target.scrollTop
  let offsetHeight = e.target.offsetHeight
  let scrollHeight = e.target.scrollHeight
  if (scrollTop + offsetHeight > scrollHeight && !isReachBottom.value) {
    isReachBottom.value = true

    // 再次查询下一页数据
    current.value++
    queryHotBlogsScroll()
  } else {
    isReachBottom.value = false
  }
}
const toShopList = (id, name) => {
  router.push({
    path: '/shopList',
    query: { type: id, name }
  })
}
const toBlogDetail = (b) => {
  router.push(`/blogDetail/${b.id}`)
}
// 跳转到个人主页
const toInfo = () => {
  router.push('/InfoHtml')
}
</script>

<template>
  <div class="home-page">
    <div class="search-bar">
      <button type="button" class="city-btn home-city" @click="cityOpen = true">
        {{ travel.selectedCity || '选城市' }} ▾
      </button>
      <div class="search-input">
        <el-input
          v-model="searchKeyword"
          size="mini"
          placeholder="输入店名、地点，回车问旅伴"
          @keyup.enter="searchPlacesInCity"
        >
          <template v-slot:prefix>
            <i class="el-input__icon el-icon-search"></i>
          </template>
        </el-input>
      </div>
      <div class="header-icon" @click="toInfo">
        <el-icon><User /></el-icon>
      </div>
    </div>
    <button type="button" class="travel-entry" @click="router.push('/travel')">
      <span class="travel-entry-icon"
        ><el-icon><MagicStick /></el-icon
      ></span>
      <span class="travel-entry-copy"
        ><strong>不知道吃什么？问问 AI 旅伴</strong
        ><small>找好店 · 看优惠 · 安排一次轻松的探店</small></span
      >
      <span class="travel-entry-action"
        >聊聊 <el-icon><ArrowRight /></el-icon
      ></span>
    </button>
    <div class="type-list">
      <div
        class="type-box"
        v-for="t in types"
        :key="t.id"
        @click="toShopList(t.id, t.name)"
      >
        <div class="type-view">
          <img :src="'src/assets/imgs' + t.icon" alt="" />
        </div>
        <div class="type-text">{{ t.name }}</div>
      </div>
    </div>
    <div class="blog-list" @scroll="onScroll">
      <div class="blog-box" v-for="b in blogs" :key="b.id">
        <div class="blog-img" @click="toBlogDetail(b)">
          <img :src="'src/assets' + b.img" alt="" />
        </div>
        <div class="blog-title">{{ b.title }}</div>
        <div class="blog-foot">
          <div class="blog-user-icon">
            <img
              :src="b.icon || 'src/assets/imgs/icons/default-icon.png'"
              alt=""
            />
          </div>
          <div class="blog-user-name">{{ b.name }}</div>
          <div class="blog-liked" @click="addLike(b)">
            <svg
              t="1646634642977"
              class="icon"
              viewBox="0 0 1024 1024"
              version="1.1"
              xmlns="http://www.w3.org/2000/svg"
              p-id="2187"
              width="14"
              height="14"
            >
              <path
                d="M160 944c0 8.8-7.2 16-16 16h-32c-26.5 0-48-21.5-48-48V528c0-26.5 21.5-48 48-48h32c8.8 0 16 7.2 16 16v448zM96 416c-53 0-96 43-96 96v416c0 53 43 96 96 96h96c17.7 0 32-14.3 32-32V448c0-17.7-14.3-32-32-32H96zM505.6 64c16.2 0 26.4 8.7 31 13.9 4.6 5.2 12.1 16.3 10.3 32.4l-23.5 203.4c-4.9 42.2 8.6 84.6 36.8 116.4 28.3 31.7 68.9 49.9 111.4 49.9h271.2c6.6 0 10.8 3.3 13.2 6.1s5 7.5 4 14l-48 303.4c-6.9 43.6-29.1 83.4-62.7 112C815.8 944.2 773 960 728.9 960h-317c-33.1 0-59.9-26.8-59.9-59.9v-455c0-6.1 1.7-12 5-17.1 69.5-109 106.4-234.2 107-364h41.6z m0-64h-44.9C427.2 0 400 27.2 400 60.7c0 127.1-39.1 251.2-112 355.3v484.1c0 68.4 55.5 123.9 123.9 123.9h317c122.7 0 227.2-89.3 246.3-210.5l47.9-303.4c7.8-49.4-30.4-94.1-80.4-94.1H671.6c-50.9 0-90.5-44.4-84.6-95l23.5-203.4C617.7 55 568.7 0 505.6 0z"
                p-id="2188"
                :fill="b.isLike ? '#ff6633' : '#82848a'"
              ></path>
            </svg>
            {{ b.liked }}
          </div>
        </div>
      </div>
    </div>
    <FootBar :active-btn="1"></FootBar>
    <CityPicker v-model="cityOpen" />
  </div>
</template>

<style>
@import '@/assets/css/main.css';
@import '@/assets/css/index.css';
.el-input__inner {
  border-radius: 20px;
}
</style>

<style scoped>
.home-city {
  border: 0;
  color: white;
  cursor: pointer;
  font: inherit;
}
.home-page {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  padding-bottom: max(8vh, 54px);
  background: #fff;
}
.home-page .search-bar {
  flex-shrink: 0;
}
.home-page .type-list {
  height: auto;
  flex-shrink: 0;
  padding: 10px 0 2px;
}
.home-page .blog-list {
  flex: 1;
  min-height: 0;
  height: auto;
}
.travel-entry {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 13px 12px 3px;
  padding: 15px;
  border: 1px solid #f1ddcf;
  border-radius: 15px;
  background: linear-gradient(105deg, #fff0e4, #f9f0fa);
  text-align: left;
  cursor: pointer;
  font-family: inherit;
}
.travel-entry-icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 39px;
  height: 39px;
  font-size: 24px;
  border-radius: 12px;
  color: white;
  background: linear-gradient(135deg, #f2a466, #dc838d);
}
.travel-entry-copy {
  flex: 1;
  min-width: 0;
}
.travel-entry-copy strong {
  display: block;
  color: #715047;
  font-size: 14px;
  font-weight: 600;
}
.travel-entry-copy small {
  display: block;
  color: #a48687;
  font-size: 10px;
  margin-top: 6px;
}
.travel-entry-action {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: #bb7a6b;
  font-size: 12px;
  white-space: nowrap;
}
@media (max-width: 360px) {
  .travel-entry {
    padding: 12px;
    gap: 8px;
  }
  .travel-entry-copy strong {
    font-size: 12px;
  }
  .travel-entry-copy small {
    font-size: 9px;
  }
}
</style>
