<script>
  import { ArrowUp, ArrowDown, Copy, Download, ChevronDown, AlertTriangle, Gauge, Zap, ChevronRight, AlertCircle, CheckCircle2, AlertOctagon, Send, Brain } from 'lucide-svelte';
  import axios from 'axios';
  import { fade, slide } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';
  import { onMount, afterUpdate } from 'svelte';
  
  let message = '';
  let response = null;
  let error = '';
  let isLoading = false;
  let collapsedSections = new Set();
  let chatHistory = [];
  let chatContainer;
  let showScrollButton = false;
  let shouldAutoScroll = true;
  let expandedResponses = new Set();
  let isAnswering = false;

  // Format metric values with units and handle different types
  function formatMetricValue(metric) {
    if (!metric) return 'N/A';
    
    // Handle object metrics (from IO metrics)
    if (typeof metric === 'object') {
      if (metric.formatted) return metric.formatted;
      if (metric.value && metric.unit) return `${formatNumber(metric.value)}${metric.unit}`;
      return JSON.stringify(metric);
    }
    
    // Handle numeric values
    if (typeof metric === 'number') {
      return formatNumber(metric);
    }
    
    return metric;
  }

  // Helper function to format numbers
  function formatNumber(value) {
    return value.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2
    });
  }

  // Get health status icon and color scheme based on status
  function getHealthStatusStyles(status) {
    const defaultStyle = {
      icon: Gauge,
      bgColor: 'bg-gray-500/10',
      borderColor: 'border-gray-500/20',
      textColor: 'text-gray-400',
      iconColor: 'text-gray-400',
      buttonBgColor: 'bg-gray-800/50',
      buttonHoverBgColor: 'hover:bg-gray-800/70'
    };

    switch (status?.toLowerCase()) {
      case 'critical':
        return {
          icon: AlertOctagon,
          bgColor: 'bg-red-500/10',
          borderColor: 'border-red-500/20',
          textColor: 'text-red-400',
          iconColor: 'text-red-400',
          buttonBgColor: 'bg-red-950/30',
          buttonHoverBgColor: 'hover:bg-red-950/50'
        };
      case 'high':
        return {
          icon: AlertTriangle,
          bgColor: 'bg-orange-500/10',
          borderColor: 'border-orange-500/20',
          textColor: 'text-orange-400',
          iconColor: 'text-orange-400',
          buttonBgColor: 'bg-orange-950/30',
          buttonHoverBgColor: 'hover:bg-orange-950/50'
        };
      case 'medium':
        return {
          icon: AlertCircle,
          bgColor: 'bg-yellow-500/10',
          borderColor: 'border-yellow-500/20',
          textColor: 'text-yellow-400',
          iconColor: 'text-yellow-400',
          buttonBgColor: 'bg-yellow-950/30',
          buttonHoverBgColor: 'hover:bg-yellow-950/50'
        };
      case 'low':
        return {
          icon: CheckCircle2,
          bgColor: 'bg-green-500/10',
          borderColor: 'border-green-500/20',
          textColor: 'text-green-400',
          iconColor: 'text-green-400',
          buttonBgColor: 'bg-green-950/30',
          buttonHoverBgColor: 'hover:bg-green-950/50'
        };
      default:
        return defaultStyle;
    }
  }

  // Get metric status color based on threshold
  function getMetricStatusColor(metric) {
    if (!metric || !metric.threshold_status) return '';
    
    switch(metric.threshold_status.toLowerCase()) {
      case 'healthy': return 'text-green-400';
      case 'warning': return 'text-yellow-400';
      case 'critical': return 'text-red-400';
      default: return '';
    }
  }

  // Get health status color for UI elements
  function getHealthStatusColor(status) {
    switch (status?.toLowerCase()) {
      case 'critical': return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'high': return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      case 'medium': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      case 'low': return 'bg-green-500/10 text-green-400 border-green-500/20';
      default: return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
    }
  }

  // Format metrics section
  function formatMetricsSection(metrics) {
    if (!metrics) return [];
    
    const sections = [];
    
    // Handle IO metrics
    if (metrics.io_metrics) {
      sections.push({
        title: 'IO Metrics',
        icon: Zap,
        metrics: Object.entries(metrics.io_metrics).map(([key, value]) => ({
          name: key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' '),
          value: formatMetricValue(value),
          status: value?.threshold_status || 'unknown',
          statusColor: getMetricStatusColor(value)
        }))
      });
    }
    
    // Handle other metrics
    const otherMetrics = Object.entries(metrics).filter(([key]) => key !== 'io_metrics');
    if (otherMetrics.length > 0) {
      sections.push({
        title: 'Other Metrics',
        icon: Gauge,
        metrics: otherMetrics.map(([key, value]) => ({
          name: key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' '),
          value: formatMetricValue(value),
          status: value?.threshold_status || 'unknown',
          statusColor: getMetricStatusColor(value)
        }))
      });
    }
    
    return sections;
  }

  // Loading states
  let loadingSteps = [
    { text: 'Analyzing database metrics...', done: false },
    { text: 'Processing performance data...', done: false },
    { text: 'Generating insights...', done: false }
  ];
  
  function resetLoadingSteps() {
    loadingSteps = loadingSteps.map(step => ({ ...step, done: false }));
  }
  
  function simulateLoadingProgress() {
    resetLoadingSteps();
    let currentStep = 0;
    
    const progressInterval = setInterval(() => {
      if (currentStep < loadingSteps.length) {
        loadingSteps[currentStep].done = true;
        loadingSteps = loadingSteps; // Trigger reactivity
        currentStep++;
      } else {
        clearInterval(progressInterval);
      }
    }, 1500);
    
    return () => clearInterval(progressInterval);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!message.trim() || isLoading) return;

    const question = message.trim();
    message = '';
    isLoading = true;
    isAnswering = true;
    error = '';

    try {
      chatHistory = [...chatHistory, { 
        question, 
        timestamp: new Date().toISOString(),
        isLoading: true 
      }];

      const response = await axios.post('http://localhost:8000/analyze/', {
        question
      });

      // Update the last chat item with the response
      chatHistory = chatHistory.map((chat, index) => {
        if (index === chatHistory.length - 1) {
          return {
            ...chat,
            response: response.data.analysis,
            isLoading: false
          };
        }
        return chat;
      });

    } catch (err) {
      error = err.response?.data?.detail || 'An error occurred while processing your request.';
      // Remove the last chat item if there was an error
      chatHistory = chatHistory.slice(0, -1);
    } finally {
      isLoading = false;
      isAnswering = false;
    }
  }

  function getHealthStatusIcon(status) {
    switch (status?.toLowerCase()) {
      case 'critical': return AlertTriangle;
      case 'high': return Zap;
      case 'medium': return Gauge;
      default: return Gauge;
    }
  }

  function toggleSection(section) {
    if (collapsedSections.has(section)) {
      collapsedSections.delete(section);
    } else {
      collapsedSections.add(section);
    }
    collapsedSections = collapsedSections;
  }

  async function copyToClipboard(text, event) {
    const button = event.currentTarget;
    try {
      await navigator.clipboard.writeText(text);
      button.classList.add('text-green-400');
      setTimeout(() => button.classList.remove('text-green-400'), 1000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }

  function getMetricTrend(value) {
    if (typeof value !== 'number') return null;
    return value > 50 ? 'high' : value > 25 ? 'medium' : 'low';
  }

  // Toggle response expansion
  function toggleResponseExpansion(timestamp) {
    if (expandedResponses.has(timestamp)) {
      expandedResponses.delete(timestamp);
    } else {
      expandedResponses.add(timestamp);
    }
    expandedResponses = expandedResponses;
  }

  // Handle scroll events
  function handleScroll() {
    if (!chatContainer) return;
    
    const { scrollTop, scrollHeight, clientHeight } = chatContainer;
    const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);
    
    // Show scroll button if we're not at the bottom
    showScrollButton = distanceFromBottom > 100;
    
    // Enable auto-scroll only if we're already near the bottom
    shouldAutoScroll = distanceFromBottom < 100;
  }

  // Scroll to bottom function
  function smoothScrollToBottom() {
    if (!chatContainer) return;
    chatContainer.scrollTo({
      top: chatContainer.scrollHeight,
      behavior: 'smooth'
    });
    shouldAutoScroll = true;
  }

  // Auto-scroll only if we haven't scrolled up
  afterUpdate(() => {
    if (shouldAutoScroll && chatContainer) {
      smoothScrollToBottom();
    }
  });

  // Add a typing animation effect
  let typingTimeout;
  function simulateTyping(text, callback) {
    clearTimeout(typingTimeout);
    let currentText = '';
    const words = text.split(' ');
    let currentIndex = 0;
    
    function typeNextWord() {
      if (currentIndex < words.length) {
        currentText += (currentIndex > 0 ? ' ' : '') + words[currentIndex];
        callback(currentText);
        currentIndex++;
        typingTimeout = setTimeout(typeNextWord, 50);
      }
    }
    
    typeNextWord();
  }
</script>

<div class="min-h-screen bg-gradient-to-b from-deep-dark via-[#1E1F23] to-deep-dark text-white flex flex-col items-center">
  <!-- Main Content Area -->
  <div class="w-full flex flex-col items-center pb-32">
    <!-- Enhanced Header -->
    <div class="flex flex-col items-center mt-10 mb-8" 
         in:fade={{duration: 800}}>
      <div class="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mb-4 shadow-lg transform hover:scale-105 transition-all duration-300">
        <span class="text-3xl">🔮</span>
      </div>
      <h1 class="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
        DB HealthWatch
      </h1>
      <p class="text-gray-400 mt-2 text-center max-w-md px-4">
        A Conversational AI Assistant
      </p>
    </div>

    <!-- Chat Container with Enhanced Styling -->
    <div class="relative w-full max-w-4xl px-4 mb-8">
      <div 
        class="w-full overflow-y-auto scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent" 
        bind:this={chatContainer}
        on:scroll={handleScroll}
        style="max-height: calc(100vh - 300px);"
      >
        {#each chatHistory as chat}
          <div class="mb-8 transform transition-all duration-300" 
               in:fade={{duration: 400, delay: 200}}>
            <!-- Question with Enhanced Styling -->
            <div class="mb-4 flex justify-between items-start group">
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-2">
                  <div class="w-8 h-8 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                    <span class="text-sm">You</span>
                  </div>
                  <p class="text-gray-400 text-sm">Asked:</p>
                </div>
                <p class="text-white pl-10">{chat.question}</p>
              </div>
              <button
                class="opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-2 hover:bg-gray-700/50 rounded-lg"
                on:click={() => copyToClipboard(chat.question)}
              >
                <Copy size={16} class="text-gray-400" />
              </button>
            </div>

            <!-- Enhanced Loading State -->
            {#if chat.isLoading}
              <div class="pl-10 space-y-4" in:fade={{duration: 200}}>
                <div class="flex items-center gap-3">
                  <div class="flex gap-1">
                    <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
                    <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
                    <span class="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
                  </div>
                  <span class="text-blue-400">Analyzing your question...</span>
                </div>
                
                <!-- Shimmer Loading Effect -->
                <div class="space-y-3">
                  <div class="h-4 bg-gray-700/50 rounded animate-pulse w-3/4"></div>
                  <div class="h-4 bg-gray-700/50 rounded animate-pulse w-1/2"></div>
                </div>
              </div>
            {:else if chat.response}
              {@const statusStyles = getHealthStatusStyles(chat.response.health_status)}
              <div class="bg-[#2C2D31]/80 backdrop-blur-sm rounded-xl p-6 hover:bg-[#2F3035] transition-all duration-300 shadow-xl border border-gray-700/30">
                <!-- Health Status with Enhanced Styling -->
                <div class="flex items-center gap-3 mb-6">
                  <div class="p-3 {statusStyles.bgColor} rounded-lg">
                    <svelte:component 
                      this={statusStyles.icon} 
                      size={24}
                      class={statusStyles.iconColor}
                    />
                  </div>
                  <div>
                    <h3 class="text-lg font-medium {statusStyles.textColor}">
                      {chat.response.health_status} Status
                    </h3>
                    <p class="text-sm text-gray-400">
                      {new Date(chat.timestamp).toLocaleString()}
                    </p>
                  </div>
                </div>

                <!-- Summary -->
                <div class="space-y-4 mb-6">
                  <p class="text-white leading-relaxed">{chat.response.summary.direct_answer}</p>
                  <p class="text-gray-400 leading-relaxed">{chat.response.summary.assessment}</p>
                </div>

                <!-- Show More Button -->
                <button
                  class={`w-full py-2 px-4 rounded-lg text-gray-300 flex items-center justify-center gap-2 transition-colors duration-200 mb-6 ${statusStyles.buttonBgColor} ${statusStyles.buttonHoverBgColor}`}
                  on:click={() => toggleResponseExpansion(chat.timestamp)}
                >
                  <span>{expandedResponses.has(chat.timestamp) ? 'Show Less' : 'Show More Details'}</span>
                  <ChevronRight
                    size={16}
                    class="transform transition-transform duration-200 {expandedResponses.has(chat.timestamp) ? 'rotate-90' : ''}"
                  />
                </button>

                {#if expandedResponses.has(chat.timestamp)}
                  <div transition:slide={{duration: 300, easing: quintOut}}>
                    <!-- Metrics -->
                    {#if chat.response.key_metrics}
                      <div class="space-y-6 mb-6">
                        {#each formatMetricsSection(chat.response.key_metrics) as section}
                          <div class="border border-gray-700/50 rounded-lg p-4">
                            <div class="flex items-center gap-2 mb-4">
                              <svelte:component this={section.icon} size={16} />
                              <h3 class="text-lg font-medium">{section.title}</h3>
                            </div>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                              {#each section.metrics as metric}
                                <div class="flex justify-between items-center p-4 bg-gray-800/30 rounded-lg hover:bg-gray-800/40 transition-colors duration-200">
                                  <div class="flex items-center gap-3">
                                    <div class={`w-2 h-2 rounded-full ${metric.statusColor || 'bg-gray-400'}`}></div>
                                    <span class="text-gray-300">{metric.name}</span>
                                  </div>
                                  <div class="flex items-center gap-2">
                                    <span class={metric.statusColor || 'text-white'}>
                                      {formatMetricValue(metric.value)}
                                    </span>
                                    {#if typeof metric.value === 'number'}
                                      <div class="w-20 h-1.5 bg-black/20 rounded-full">
                                        <div 
                                          class="h-full rounded-full bg-deep-blue transition-all duration-500" 
                                          style="width: {Math.min(metric.value, 100)}%"
                                        />
                                      </div>
                                    {/if}
                                  </div>
                                </div>
                              {/each}
                            </div>
                          </div>
                        {/each}
                      </div>
                    {/if}

                    <!-- Performance Impact -->
                    {#if chat.response.performance_impact}
                      <div class="border border-gray-700/50 rounded-lg p-4 mb-6">
                        <h3 class="text-lg font-medium mb-4">Performance Impact</h3>
                        <div class="space-y-2">
                          {#each Object.entries(chat.response.performance_impact) as [key, value]}
                            <div class="flex justify-between items-center p-2 bg-gray-800/30 rounded">
                              <span class="text-gray-300">
                                {key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}
                              </span>
                              <span class="text-white">{formatMetricValue(value)}</span>
                            </div>
                          {/each}
                        </div>
                      </div>
                    {/if}

                    <!-- Recommendations -->
                    {#if chat.response.recommendations && chat.response.recommendations.length > 0}
                      <div class="border border-gray-700/50 rounded-lg p-4">
                        <div class="flex items-center gap-2 mb-4">
                          <AlertTriangle size={16} class="text-deep-blue" />
                          <h3 class="text-lg font-medium">Recommendations</h3>
                        </div>
                        <div class="space-y-4">
                          {#each chat.response.recommendations as rec, i}
                            <div class="p-4 bg-gray-800/30 rounded-lg border-l-4 border-deep-blue hover:bg-gray-800/40 transition-colors duration-200">
                              <div class="flex items-start gap-4">
                                <div class="bg-deep-blue/20 text-deep-blue px-2.5 py-1 rounded-lg text-sm font-medium">
                                  #{i + 1}
                                </div>
                                <div class="flex-1">
                                  <p class="text-white font-medium mb-2">{rec.fix}</p>
                                  <p class="text-gray-400 text-sm leading-relaxed">{rec.benefit}</p>
                                </div>
                              </div>
                            </div>
                          {/each}
                        </div>
                      </div>
                    {/if}
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>

      <!-- Enhanced Floating Scroll Button -->
      {#if showScrollButton}
        <button
          class="fixed bottom-32 right-8 p-3 bg-blue-600 hover:bg-blue-700 rounded-full shadow-lg transform hover:scale-105 transition-all duration-300"
          on:click={smoothScrollToBottom}
          in:fade={{duration: 200}}
        >
          <ArrowDown size={20} />
        </button>
      {/if}
    </div>

    <!-- Enhanced Error Message -->
    {#if error}
      <div class="w-full max-w-3xl px-4 mb-8" 
           transition:slide|local={{duration: 300}}>
        <div class="bg-red-500/10 backdrop-blur-sm border border-red-500/20 rounded-xl p-4 text-red-400 flex items-center gap-3">
          <AlertOctagon size={20} />
          <p>{error}</p>
        </div>
      </div>
    {/if}
  </div>

  <!-- Enhanced Question Box -->
  <div class="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-deep-dark via-deep-dark to-transparent pt-8 pb-8">
    <div class="max-w-3xl mx-auto px-4">
      <form
        on:submit|preventDefault={handleSubmit}
        class="relative"
      >
        <input
          type="text"
          bind:value={message}
          placeholder={isAnswering ? "Analyzing your previous question..." : "Ask DB HealthWatch..."}
          class="w-full bg-[#2C2D31]/80 backdrop-blur-sm text-white rounded-xl px-6 py-4 pr-12 border border-gray-700/30 focus:border-blue-500/50 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all duration-300"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !message.trim()}
          class="absolute right-3 top-1/2 -translate-y-1/2 p-2 {isLoading ? 'bg-gray-700' : 'bg-blue-600 hover:bg-blue-700'} disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg transform hover:scale-105 transition-all duration-300"
        >
          {#if isLoading}
            <div class="w-5 h-5 border-2 border-gray-400 border-t-white rounded-full animate-spin"></div>
          {:else}
            <Send size={20} />
          {/if}
        </button>
      </form>
      
      <!-- Loading Status Bar -->
      {#if isAnswering}
        <div class="absolute -top-6 left-0 right-0 flex justify-center" in:fade={{duration: 200}}>
          <div class="bg-blue-600/20 backdrop-blur-sm px-4 py-2 rounded-full flex items-center gap-2 text-sm text-blue-400">
            <div class="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"></div>
            <span>Processing your question...</span>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

<style lang="postcss">
  :global(body) {
    background-color: #1a1b1e;
  }
  
  /* Custom Scrollbar */
  .scrollbar-thin::-webkit-scrollbar {
    width: 6px;
  }
  
  .scrollbar-thin::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .scrollbar-thin::-webkit-scrollbar-thumb {
    background: #4B5563;
    border-radius: 3px;
  }
  
  .scrollbar-thin::-webkit-scrollbar-thumb:hover {
    background: #6B7280;
  }
</style>
