/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect, useRef } from 'react';
import { 
  Sparkles, 
  Settings, 
  MessageSquare, 
  Loader2,
  FileText,
  Layers,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Database,
  Ruler,
  Terminal,
  Download,
  Plus,
  History,
  Layout,
  Folder,
  RefreshCw,
  Zap,
  Info,
  Cpu,
  Globe,
  Lock,
  ChevronRight,
  Eye,
  EyeOff,
  Trash2
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import Markdown from 'react-markdown';
import logoImg from '../logo.jpg';
import { GoogleGenAI } from "@google/genai";
import { cn } from './lib/utils';

// Types
type Category = 'consulting' | 'river' | 'drainage';
type ArtifactType = 'report' | 'drawing' | 'analysis' | 'none';
type ModelType = 'gemini' | 'openai' | 'local';

interface ModelConfig {
  type: ModelType;
  modelName: string;
  apiKey: string;
  baseUrl: string;
}

interface EmbeddingConfig {
  model: string;
  apiKey: string;
  baseUrl: string;
}

interface VisionConfig {
  model: string;
  apiKey: string;
  baseUrl: string;
}

// Initialize Gemini Client
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY || "" });

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

interface Project {
  id: string;
  name: string;
  description: string;
  category?: Category;
}

interface UserProfile {
  id?: string;
  name: string;
  email: string;
  avatar_initial: string;
  updated_at?: string;
}

export default function App() {
  const [currentCategory, setCurrentCategory] = useState<Category>('river');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: "您好！我是您的水利设计助理。您可以让我为您生成设计报告、分析地形数据或进行规范核对。请问今天有什么可以帮您？",
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'chat' | 'workspace'>('chat');
  const [activeArtifact, setActiveArtifact] = useState<ArtifactType>('report');
  const [showKB, setShowKB] = useState(false);
  const [showParams, setShowParams] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showProjects, setShowProjects] = useState(false);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<{
    id: string; name: string; pages: {page_num: number; text: string}[];
    currentPage: number; page_count: number | null;
    images: {id: string; page: number; image_index: number; description?: string}[];
  } | null>(null);
  const [newProjectCategory, setNewProjectCategory] = useState<Category>('river');
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [systemStatus, setSystemStatus] = useState<string>('idle');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load AI Config from localStorage
  const loadAiConfig = (): ModelConfig => {
    try {
      const saved = localStorage.getItem('aiConfig');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { type: 'gemini', modelName: 'gemini-3-flash-preview', apiKey: process.env.GEMINI_API_KEY || '', baseUrl: 'https://api.openai.com/v1' };
  };

  const [aiConfig, setAiConfig] = useState<ModelConfig>(loadAiConfig);

  // Load Embedding Config from localStorage
  const loadEmbeddingConfig = (): EmbeddingConfig => {
    try {
      const saved = localStorage.getItem('embeddingConfig');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { model: 'BAAI/bge-large-zh-v1.5', apiKey: '', baseUrl: 'https://api.siliconflow.cn/v1' };
  };

  const [embeddingConfig, setEmbeddingConfig] = useState<EmbeddingConfig>(loadEmbeddingConfig);

  // Load Vision Config from localStorage
  const loadVisionConfig = (): VisionConfig => {
    try {
      const saved = localStorage.getItem('visionConfig');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { model: 'Qwen/Qwen3-VL-32B-Instruct', apiKey: '', baseUrl: 'https://api.siliconflow.cn/v1' };
  };

  const [visionConfig, setVisionConfig] = useState<VisionConfig>(loadVisionConfig);

  // Save Embedding Config to localStorage
  useEffect(() => {
    try { localStorage.setItem('embeddingConfig', JSON.stringify(embeddingConfig)); } catch (e) {}
  }, [embeddingConfig]);

  // Save Vision Config to localStorage
  useEffect(() => {
    try { localStorage.setItem('visionConfig', JSON.stringify(visionConfig)); } catch (e) {}
  }, [visionConfig]);

  // Save AI Config to localStorage
  useEffect(() => {
    try { localStorage.setItem('aiConfig', JSON.stringify(aiConfig)); } catch (e) {}
  }, [aiConfig]);

  // Load User Profile from localStorage
  const loadUserProfile = (): UserProfile => {
    try {
      const saved = localStorage.getItem('userProfile');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { name: '张工程师', email: 'yulaitage@gmail.com', avatar_initial: '张' };
  };

  const [userProfile, setUserProfile] = useState<UserProfile>(loadUserProfile);

  // Save User Profile to localStorage
  useEffect(() => {
    try { localStorage.setItem('userProfile', JSON.stringify(userProfile)); } catch (e) {}
  }, [userProfile]);

  // Fetch user profile from backend on mount
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await fetch('/api/user/profile');
        if (res.ok) {
          const data = await res.json();
          setUserProfile({ name: data.name, email: data.email, avatar_initial: data.avatar_initial, id: data.id, updated_at: data.updated_at });
        }
      } catch (e) {
        // Fallback to localStorage value
      }
    };
    fetchProfile();
  }, []);

  // Load projects from localStorage
  const loadProjects = (): Project[] => {
    try {
      const saved = localStorage.getItem('projects');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return [
      { id: '1', name: 'XX 河道治理工程', description: '河道整治与堤防加固方案设计。', category: 'river' },
      { id: '2', name: 'YY 市给排水规划', description: '市政水务系统管网初步设计。', category: 'drainage' },
      { id: '3', name: 'ZZ 江水情监控系统', description: '水闸自动控制与实时监控平台。', category: 'consulting' }
    ];
  };

  const [projects, setProjects] = useState<Project[]>(loadProjects);
  const [projectInfo, setProjectInfo] = useState<Project | null>(null);

  // Save projects to localStorage
  useEffect(() => {
    try { localStorage.setItem('projects', JSON.stringify(projects)); } catch (e) {}
  }, [projects]);

  // Initialize projectInfo
  useEffect(() => {
    const loaded = loadProjects();
    if (loaded.length > 0 && !projectInfo) setProjectInfo(loaded[0]);
  }, []);

  // AI Configuration State - now loaded from localStorage via loadAiConfig

  const [showApiKey, setShowApiKey] = useState(false);
  const [showEmbeddingApiKey, setShowEmbeddingApiKey] = useState(false);
  const [showVisionApiKey, setShowVisionApiKey] = useState(false);

  const [kbItems, setKbItems] = useState<{id: string; type: string; name: string; size: string}[]>([]);

  // Load documents from backend on mount
  useEffect(() => {
    fetch('/api/knowledge-base/documents')
      .then(r => r.json())
      .then((docs: any[]) => {
        const categoryMap: Record<string, string> = { planning: '规划', spec: '规范', case: '案例' };
        setKbItems(docs.map(d => ({
          id: d.id,
          type: categoryMap[d.category] || d.category || '其他',
          name: d.title || d.filename,
          size: d.size ? (d.size / 1024 / 1024).toFixed(1) + 'MB' : '',
        })));
      })
      .catch(() => {});
  }, []);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const [params, setParams] = useState([
    { label: '堤顶高度', value: '142.5', unit: 'm', id: 'H_crown' },
    { label: '底宽 (B)', value: '6.0', unit: 'm', id: 'B_bottom' },
    { label: '内坡比', value: '1:3.0', unit: '', id: 'm_slope' },
    { label: '设计流量 Q', value: '5230', unit: 'm³/s', id: 'Q_flow' },
  ]);

  // Handle Category Change
  useEffect(() => {
    const welcomeMessages = {
      consulting: "已切换至 **水务咨询模块**。我们可以辅助您编制水利规划、水资源论证或节水评估等咨询类报告。",
      river: "已切换至 **河道设计模块**。我已准备好进行河道整治方案编制、断面优化及 CAD 图纸快速绘制。",
      drainage: "已切换至 **给排水设计模块**。我可以协助您进行市政给排水管网布置、海绵城市计算及相关设计说明编制。"
    };
    setMessages([{
      id: Date.now().toString(),
      role: 'assistant',
      content: welcomeMessages[currentCategory]
    }]);
    setActiveArtifact(currentCategory === 'consulting' ? 'report' : 'drawing');
  }, [currentCategory]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Scroll to bottom when switching to chat view
  useEffect(() => {
    if (viewMode === 'chat') {
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
  }, [viewMode]);

  // Handle send (Multi-Model AI Routing)
  const handleSend = async () => {
    console.log('=== handleSend called ===');
    console.log('chatInput:', chatInput);
    console.log('projectInfo:', projectInfo);
    if (!chatInput.trim()) return;
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: chatInput };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setChatInput('');
    setIsLoading(true);
    setSystemStatus('hydraulic');

    try {
      console.log('=== Starting AI request ===');
      const systemPrompt = `You are an expert Water Engineering AI Assistant specialized in ${currentCategory}.
      Current categories: consulting (planning/evaluation), river (channel design/levee), drainage (pipe networks).
      Provide technical advice, refer to Chinese national standards like GB 50286 or GB 50707 where applicable.
      Keep responses professional and concise. Use Markdown.`;

      let aiContent = "";

      if (aiConfig.type === 'gemini') {
        const response = await ai.models.generateContent({
          model: aiConfig.modelName || "gemini-3-flash-preview",
          contents: updatedMessages.map(m => ({
            role: m.role === 'user' ? 'user' : 'model',
            parts: [{ text: m.content }]
          })),
          config: { systemInstruction: systemPrompt }
        });
        aiContent = response.text || "AI 引擎未返回结果。";
      } else {
        // OpenAI or Local (OpenAI-Compatible) or Backend API
        let apiUrl = aiConfig.baseUrl;
        let headers: Record<string, string> = {
          'Content-Type': 'application/json'
        };
        let body: any = {
          model: aiConfig.modelName,
          messages: [
            { role: 'system', content: systemPrompt },
            ...updatedMessages.map(m => ({
              role: m.role,
              content: m.content
            }))
          ]
        };

        // Check if should use backend API (route through backend for all preset providers)
        console.log('aiConfig:', aiConfig);
        const useBackend = aiConfig.type !== 'gemini';
        console.log('useBackend:', useBackend);
        if (useBackend) {
          // Route through backend
          const projectId = projectInfo?.id || 'default';
          apiUrl = '/api/chat';
          // project_id_str for string IDs like "1", project_id only for valid UUIDs
          const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(projectId);
          body = {
            ...(isUUID ? { project_id: projectId } : { project_id_str: projectId }),
            message: chatInput,
            context: { category: currentCategory },
            model_name: aiConfig.modelName,
            api_key: aiConfig.apiKey,
            base_url: aiConfig.baseUrl === '/api' ? '' : aiConfig.baseUrl,
          };
          console.log('Sending to backend:', body);
          headers = { 'Content-Type': 'application/json' };
        } else {
          // Direct API call (only for Gemini which uses Google AI API)
          console.log('Using Gemini direct API');
          if (aiConfig.apiKey) {
            headers['Authorization'] = `Bearer ${aiConfig.apiKey}`;
          }
        }

        console.log('Fetching:', apiUrl, body);

        const response = await fetch(apiUrl, {
          method: 'POST',
          headers,
          body: JSON.stringify(body)
        });

        console.log('Response status:', response.status);

        // Parse response
        const text = await response.text();
        console.log('Response text:', text.substring(0, 500));

        let data;
        try {
          data = JSON.parse(text);
        } catch (e) {
          throw new Error(`Invalid JSON response: ${text.substring(0, 200)}`);
        }

        if (!response.ok) {
           throw new Error(data.detail || data.error?.message || `API Error ${response.status}`);
        }

        // Backend returns {conversation_id, message, intent, ...} format
        console.log('data keys:', Object.keys(data));
        console.log('data.message length:', data.message?.length);
        console.log('data.content:', data.content);
        aiContent = data.message || data.content || data.text || "AI 引擎未返回结果。";
        console.log('aiContent:', aiContent.substring(0, 100));
      }

      console.log('=== Setting messages with aiContent length:', aiContent.length);
      console.log('aiContent first 100 chars:', aiContent.substring(0, 100));
      setSystemStatus('cad');
      const newMsg = {
        id: Date.now().toString(),
        role: 'assistant' as const,
        content: aiContent
      };
      console.log('newMsg content length:', newMsg.content.length);
      console.log('newMsg:', JSON.stringify(newMsg).substring(0, 200));
      setMessages(prev => {
        console.log('prev.length:', prev.length, ' Adding new message');
        return [...prev, newMsg]
      });
      console.log('=== Messages set ===');
    } catch (err: any) {
      console.error('Chat error:', err);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `抱歉，AI 引擎 [${aiConfig.type}] 计算出现异常: ${err.message || "请检查网络或配置。"}`
      }]);
    } finally {
      setIsLoading(false);
      setSystemStatus('idle');
    }
  };

  // Handle Document Preview
  const handlePreviewDoc = async (id: string, name: string) => {
    setPreviewDoc({ id, name, pages: [], currentPage: 0, page_count: null, images: [] });
    try {
      const [previewRes, imagesRes] = await Promise.all([
        fetch(`/api/knowledge-base/documents/${id}/preview`),
        fetch(`/api/knowledge-base/images/${id}`),
      ]);
      if (!previewRes.ok) throw new Error(`HTTP ${previewRes.status}`);
      const data = await previewRes.json();
      const images = imagesRes.ok ? await imagesRes.json() : [];
      setPreviewDoc({
        id, name: data.title || name,
        pages: data.pages || [],
        currentPage: 0,
        page_count: data.page_count,
        images: images || [],
      });
    } catch {
      setPreviewDoc(null);
      alert('预览加载失败');
    }
  };

  // Handle Delete Document
  const handleDeleteDoc = async (id: string, name: string) => {
    if (!confirm(`确定要删除「${name}」吗？相关数据库记录和文件将一并删除。`)) return;
    try {
      const res = await fetch(`/api/knowledge-base/documents/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setKbItems(prev => prev.filter(item => item.id !== id));
    } catch (err: any) {
      alert(`删除失败: ${err.message}`);
    }
  };

  // Handle File Upload
  const [uploadCategory, setUploadCategory] = useState<'planning' | 'spec' | 'case'>('planning');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [uploadError, setUploadError] = useState<string | null>(null);

  const pollUploadStatus = async (taskId: string, filename: string, fileSize: string, typeLabel: string) => {
    const poll = async (): Promise<void> => {
      try {
        const res = await fetch(`/api/knowledge-base/upload/status/${taskId}`);
        if (!res.ok) return;
        const status = await res.json();

        if (status.status === 'processing') {
          setUploadProgress(status.message || '处理中...');
          setTimeout(poll, 3000);
        } else if (status.status === 'done') {
          const r = status.result;
          setKbItems(prev => [
            { id: r.fileId, type: typeLabel, name: filename, size: fileSize },
            ...prev
          ]);
          setIsUploading(false);
          setUploadProgress('');
          setSystemStatus('idle');
        } else if (status.status === 'error') {
          setUploadError(status.message || '处理失败');
          setIsUploading(false);
          setUploadProgress('');
          setSystemStatus('idle');
        }
      } catch {
        setTimeout(poll, 5000);
      }
    };
    poll();
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);
    setUploadProgress('正在上传文件...');
    setSystemStatus('export');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('category', uploadCategory);

    try {
      const response = await fetch('/api/knowledge-base/upload', {
        method: 'POST',
        body: formData
      });
      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || `HTTP ${response.status}`);
      }
      const data = await response.json();

      const typeLabel = uploadCategory === 'spec' ? '规范' : uploadCategory === 'case' ? '案例' : '规划';
      const fileSize = (file.size / 1024 / 1024).toFixed(1) + 'MB';

      if (data.status === 'accepted' && data.taskId) {
        setUploadProgress('文件已上传，正在后台处理...');
        pollUploadStatus(data.taskId, file.name, fileSize, typeLabel);
      } else {
        setKbItems(prev => [
          { id: data.fileId, type: typeLabel, name: file.name, size: fileSize },
          ...prev
        ]);
        setIsUploading(false);
        setUploadProgress('');
        setSystemStatus('idle');
      }
    } catch (err: any) {
      setUploadError(err?.message || '上传失败');
      setIsUploading(false);
      setUploadProgress('');
      setSystemStatus('idle');
    } finally {
      e.target.value = '';
    }
  };

  // Handle Sync Params
  const handleSyncParams = async () => {
    setSystemStatus('hydraulic');
    try {
      const response = await fetch('/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ params, category: currentCategory })
      });
      const data = await response.json();
      
      if (data.status === 'success') {
        const aiResponse = data.warnings.length > 0 
          ? `[系统预警] ${data.warnings.join(' ')}`
          : `[计算引擎] 参数校验已通过。${data.notices[0]}`;
          
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: aiResponse
        }]);
      }
    } catch (err) {
      console.error('Calculation error:', err);
    } finally {
      setSystemStatus('idle');
    }
  };

  return (
    <div className="flex h-screen bg-[#0D0D0D] text-[#D1D1D1] font-sans selection:bg-blue-500/30 overflow-hidden">
      
      {/* 1. Slim Sidebar - Minimalist rail */}
      <aside className="w-16 border-r border-[#262626] flex flex-col items-center py-6 gap-6 bg-[#0D0D0D] z-50">
        <div className="w-12 h-12 bg-transparent flex items-center justify-center mb-4 relative group cursor-pointer" title="IRD WaterDesign AI">
           <div className="relative flex items-center justify-center w-full h-full p-1.5 bg-[#1A1A1A] border border-[#262626] rounded-xl overflow-hidden group-hover:border-blue-500/50 transition-colors shadow-inner">
             <img 
               src={logoImg} 
               alt="IRD Logo" 
               className="w-full h-full object-contain filter drop-shadow-md group-hover:scale-110 transition-transform duration-500 rounded-lg" 
               referrerPolicy="no-referrer"
             />
             {/* Subtle overlay for depth */}
             <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
           </div>
        </div>
        
        {/* New Project Quick Action */}
        <div className="flex flex-col items-center gap-1 w-full px-2 border-b border-[#262626] pb-6">
           <button 
             title="新建项目" 
             onClick={() => setShowNewProjectModal(true)}
             className="w-10 h-10 flex items-center justify-center bg-[#1A1A1A] text-slate-200 hover:bg-[#262626] rounded-xl transition-all group relative active:scale-95"
           >
              <Plus className="w-5 h-5 group-hover:scale-110 transition-transform" />
           </button>
        </div>

        <nav className="flex flex-col gap-4">
           {[
             { icon: Folder, id: 'projects', label: '项目管理', action: () => { setShowProjects(!showProjects); setShowHistory(false); setShowKB(false); setShowSettings(false); } },
             { icon: MessageSquare, id: 'chat', label: '对话', action: () => { setViewMode('chat'); setShowProjects(false); setShowHistory(false); setShowKB(false); setShowSettings(false); } },
             { icon: Layout, id: 'workspace', label: '工作空间', action: () => { setViewMode('workspace'); setShowProjects(false); setShowHistory(false); setShowKB(false); setShowSettings(false); setActiveArtifact('report'); } },
             { icon: History, id: 'history', label: '历史版本', action: () => { setShowHistory(!showHistory); setShowProjects(false); setShowKB(false); setShowSettings(false); } },
             { icon: Database, id: 'kb', label: '知识库', action: () => { setShowKB(!showKB); setShowProjects(false); setShowHistory(false); setShowSettings(false); } },
           ].map((item) => (
             <button 
               key={item.id} 
               title={item.label} 
               onClick={item.action}
               className={cn(
                 "p-3 rounded-xl transition-all relative group",
                 ((item.id === 'kb' && showKB) || 
                  (item.id === 'projects' && showProjects) || 
                  (item.id === 'history' && showHistory) ||
                  (item.id === 'chat' && viewMode === 'chat' && !showKB && !showProjects && !showHistory && !showSettings) ||
                  (item.id === 'workspace' && viewMode === 'workspace' && !showKB && !showProjects && !showHistory && !showSettings))
                   ? "text-blue-500 bg-blue-500/10 shadow-[0_0_15px_rgba(59,130,246,0.1)]" 
                   : "text-slate-500 hover:text-slate-200 hover:bg-[#1A1A1A]"
               )}
             >
               <item.icon className="w-5 h-5" />
               {((item.id === 'chat' && viewMode === 'chat' && !showKB && !showProjects && !showHistory && !showSettings) ||
                 (item.id === 'workspace' && viewMode === 'workspace' && !showKB && !showProjects && !showHistory && !showSettings)) && (
                 <motion.div layoutId="nav-glow" className="absolute -left-1 w-1 h-6 bg-blue-500 rounded-r-full shadow-[0_0_10px_rgba(59,130,246,0.5)]" />
               )}
             </button>
           ))}
        </nav>

        <div className="mt-auto flex flex-col gap-4">
           <button 
            onClick={() => { setShowSettings(!showSettings); setShowProjects(false); setShowHistory(false); setShowKB(false); }}
            className={cn(
              "p-3 transition-all rounded-xl",
              showSettings ? "text-blue-500 bg-blue-500/10" : "text-slate-500 hover:text-slate-200 hover:bg-[#1A1A1A]"
            )}
           >
             <Settings className="w-5 h-5" />
           </button>
           <div className="w-8 h-8 rounded-full bg-blue-600/10 border border-blue-500/30 flex items-center justify-center text-[10px] font-bold text-blue-500">
             {userProfile.avatar_initial || '张'}
           </div>
        </div>
      </aside>

      {/* 2. Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
         
         {/* Left: Chat Control Panel (Claude Style) */}
         <section className={cn(
           "flex flex-col border-[#262626] bg-[#0F0F0F] relative transition-all duration-500 ease-in-out shrink-0 h-full overflow-hidden",
           viewMode === 'chat' ? "w-full border-0 px-20 lg:px-40" : "w-[440px] border-r"
         )}>
            <div className={cn(
              "flex flex-col mx-auto transition-all duration-500 w-full h-full min-h-0",
              viewMode === 'chat' ? "max-w-4xl" : "max-w-none"
            )}>
              {/* Knowledge Base Overlay Panel */}
            <AnimatePresence>
               {showKB && (
                 <motion.div 
                   initial={{ x: -20, opacity: 0 }}
                   animate={{ x: 0, opacity: 1 }}
                   exit={{ x: -20, opacity: 0 }}
                   className="absolute inset-0 z-40 bg-[#0F0F0F] flex flex-col"
                 >
                    <header className="px-6 py-5 border-b border-[#262626] flex items-center justify-between shrink-0">
                       <div className="flex items-center gap-3 min-w-0">
                          {previewDoc && (
                            <button onClick={() => setPreviewDoc(null)} className="p-1.5 text-slate-500 hover:text-white hover:bg-[#1A1A1A] rounded-lg transition-all shrink-0">
                              <ArrowRight className="w-4 h-4 rotate-180" />
                            </button>
                          )}
                          <div className="min-w-0">
                             <h2 className="text-sm font-bold text-white truncate">
                               {previewDoc ? previewDoc.name : '工程知识库'}
                             </h2>
                             {!previewDoc && (
                               <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-widest font-mono">Knowledge Management System</p>
                             )}
                          </div>
                       </div>
                       <button onClick={() => { setShowKB(false); setPreviewDoc(null); }} className="p-2 hover:bg-[#1A1A1A] rounded-lg text-slate-500">
                          <Plus className="w-4 h-4 rotate-45" />
                       </button>
                    </header>

                    <div className="flex flex-1 min-h-0">
                    {/* Left: File List & Upload (shrinks when previewing) */}
                    <div className={cn(
                      "flex flex-col min-h-0 overflow-hidden transition-all duration-300",
                      previewDoc ? "w-[400px] border-r border-[#262626]" : "w-full"
                    )}>
                    <div className={cn(
                      "flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar",
                      previewDoc && "p-4 space-y-5"
                    )}>
                       {/* Category Selection */}
                       <div className="flex gap-2">
                         <button
                           onClick={() => setUploadCategory('planning')}
                           className={cn(
                             "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                             uploadCategory === 'planning'
                               ? "bg-amber-600 text-white"
                               : "bg-[#1A1A1A] text-slate-400 hover:bg-[#262626]"
                           )}
                         >
                           规划
                         </button>
                         <button
                           onClick={() => setUploadCategory('spec')}
                           className={cn(
                             "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                             uploadCategory === 'spec'
                               ? "bg-blue-600 text-white"
                               : "bg-[#1A1A1A] text-slate-400 hover:bg-[#262626]"
                           )}
                         >
                           规范
                         </button>
                         <button
                           onClick={() => setUploadCategory('case')}
                           className={cn(
                             "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                             uploadCategory === 'case'
                               ? "bg-emerald-600 text-white"
                               : "bg-[#1A1A1A] text-slate-400 hover:bg-[#262626]"
                           )}
                         >
                           案例
                         </button>
                       </div>

                       {/* Upload Zone */}
                       <input
                         type="file"
                         ref={fileInputRef}
                         className="hidden"
                         onChange={handleFileUpload}
                         accept=".pdf,.doc,.docx,.txt"
                         disabled={isUploading}
                       />
                       <div
                        onClick={() => !isUploading && fileInputRef.current?.click()}
                        className={cn(
                          "border-2 border-dashed rounded-2xl p-8 transition-all group flex flex-col items-center justify-center gap-3 bg-[#141414] cursor-pointer",
                          isUploading
                            ? "border-blue-500/50 opacity-60 pointer-events-none"
                            : "border-[#262626] hover:border-blue-500/50",
                        )}
                       >
                          <div className="w-12 h-12 bg-blue-600/10 rounded-full flex items-center justify-center text-blue-500 group-hover:scale-110 transition-transform">
                             {isUploading ? (
                               <RefreshCw className="w-6 h-6 animate-spin" />
                             ) : (
                               <Plus className="w-6 h-6" />
                             )}
                          </div>
                          <div className="text-center">
                             <p className="text-xs font-bold text-slate-300">
                               {isUploading ? (uploadProgress || '处理中...') : '点击或拖拽上传文件'}
                             </p>
                             <p className="text-[10px] text-slate-600 mt-1">支持 PDF, CAD, Word, Excel (Max 50MB)</p>
                          </div>
                       </div>

                       {/* Upload Error */}
                       {uploadError && (
                         <div className="flex items-center gap-2 p-3 bg-red-600/10 border border-red-500/30 rounded-xl">
                           <span className="text-red-400 text-xs">{uploadError}</span>
                           <button
                             onClick={() => setUploadError(null)}
                             className="ml-auto text-red-400 hover:text-red-300 text-xs"
                           >
                             ✕
                           </button>
                         </div>
                       )}

                       {/* Categories */}
                       <div className="space-y-4">
                          <h3 className="text-[10px] font-bold text-slate-600 uppercase tracking-widest">最近库文件</h3>
                          <div className="space-y-2">
                             {kbItems.map(item => (
                               <div key={item.id} className="p-3 bg-[#141414] border border-[#262626] rounded-xl flex items-center justify-between group hover:border-blue-500/30 transition-all cursor-pointer" onClick={() => handlePreviewDoc(item.id, item.name)}>
                                  <div className="flex items-center gap-3 min-w-0">
                                     <div className={cn(
                                       "px-1.5 py-0.5 rounded text-[8px] font-bold uppercase shrink-0",
                                       item.type === '规范' ? "bg-blue-600/10 text-blue-500" :
                                       item.type === '规划' ? "bg-amber-600/10 text-amber-500" :
                                       "bg-emerald-600/10 text-emerald-500"
                                     )}>
                                        {item.type}
                                     </div>
                                     <span className="text-xs text-slate-300 font-medium truncate">{item.name}</span>
                                  </div>
                                  <div className="flex items-center gap-2 shrink-0">
                                     <span className="text-[10px] text-slate-600 font-mono opacity-0 group-hover:opacity-100 transition-opacity">{item.size}</span>
                                     <button
                                       onClick={(e) => { e.stopPropagation(); handleDeleteDoc(item.id, item.name); }}
                                       className="p-1 text-slate-600 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all rounded hover:bg-red-600/10"
                                       title="删除"
                                     >
                                       <Trash2 className="w-3.5 h-3.5" />
                                     </button>
                                  </div>
                               </div>
                             ))}
                          </div>
                       </div>

                       <div className="p-4 bg-blue-600/5 border border-blue-600/20 rounded-xl">
                          <p className="text-[10px] text-blue-500 leading-relaxed">
                             <Sparkles className="w-3 h-3 inline mr-1 mb-0.5" />
                             AI 正在对知识库文件进行深度索引。上传后，您可以在对话中直接引用相关案例或规范。
                          </p>
                       </div>
                    </div>
                    </div>

                    {/* Right: Preview Content */}
                    {previewDoc && (
                      <div className="flex-1 flex flex-col min-h-0 items-center">
                        <div className="flex-1 overflow-y-auto py-5 custom-scrollbar w-full flex justify-center">
                          <div className="w-full max-w-[21cm] bg-[#141414] border border-[#262626] rounded-lg min-h-[29.7cm] px-[2cm] py-[2.5cm] shadow-lg">
                            {previewDoc.pages.length === 0 ? (
                              <div className="flex items-center justify-center h-full">
                                <Loader2 className="w-5 h-5 text-slate-600 animate-spin" />
                              </div>
                            ) : (
                              <div>
                                {previewDoc.pages[previewDoc.currentPage]?.text && (
                                  <div className="whitespace-pre-wrap text-[13px] leading-[1.8] text-slate-300 font-[system-ui]">
                                    {previewDoc.pages[previewDoc.currentPage].text}
                                  </div>
                                )}
                                {previewDoc.images.filter(img => img.page === previewDoc.currentPage + 1).map(img => (
                                  <div key={img.id} className="mt-4 mb-2">
                                    <img
                                      src={`/api/knowledge-base/images/${previewDoc.id}/page/${img.page}/img/${img.image_index}`}
                                      alt={img.description || `Page ${img.page} Image`}
                                      className="max-w-full rounded border border-[#333]"
                                      loading="lazy"
                                    />
                                    {img.description && (
                                      <p className="text-[11px] text-slate-500 mt-1 italic">{img.description}</p>
                                    )}
                                  </div>
                                ))}
                                {!previewDoc.pages[previewDoc.currentPage]?.text &&
                                  previewDoc.images.filter(img => img.page === previewDoc.currentPage + 1).length === 0 &&
                                  <p className="text-slate-600 text-[13px]">该页无文本内容</p>
                                }
                              </div>
                            )}
                          </div>
                        </div>
                        {previewDoc.pages.length > 0 && (
                          <div className="flex items-center justify-between px-6 py-3 border-t border-[#262626] bg-[#0D0D0D] shrink-0">
                            <button
                              onClick={() => setPreviewDoc(p => p ? {...p, currentPage: Math.max(0, p.currentPage - 1)} : null)}
                              disabled={previewDoc.currentPage === 0}
                              className="px-3 py-1.5 text-xs text-slate-400 hover:text-white bg-[#1A1A1A] rounded-lg disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                            >上一页</button>
                            <span className="text-[11px] text-slate-500 font-mono">
                              第 {previewDoc.currentPage + 1} 页 / 共 {previewDoc.pages.length} 页
                            </span>
                            <button
                              onClick={() => setPreviewDoc(p => p ? {...p, currentPage: Math.min(p.pages.length - 1, p.currentPage + 1)} : null)}
                              disabled={previewDoc.currentPage >= previewDoc.pages.length - 1}
                              className="px-3 py-1.5 text-xs text-slate-400 hover:text-white bg-[#1A1A1A] rounded-lg disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                            >下一页</button>
                          </div>
                        )}
                      </div>
                    )}
                    </div>
                 </motion.div>
               )}

               {showProjects && (
                 <motion.div 
                   initial={{ x: -20, opacity: 0 }}
                   animate={{ x: 0, opacity: 1 }}
                   exit={{ x: -20, opacity: 0 }}
                   className="absolute inset-0 z-40 bg-[#0F0F0F] flex flex-col"
                 >
                    <header className="px-6 py-6 border-b border-[#262626] flex items-center justify-between font-bold">
                       <div>项目管理</div>
                       <button onClick={() => setShowProjects(false)} className="p-2 hover:bg-[#1A1A1A] rounded-lg text-slate-500">
                          <Plus className="w-4 h-4 rotate-45" />
                       </button>
                    </header>
                    <div className="p-6 space-y-4 overflow-y-auto flex-1 custom-scrollbar">
                       {projects.map((p) => (
                         <div 
                           key={p.id} 
                           onClick={() => {
                             setProjectInfo(p);
                             setShowProjects(false);
                             setMessages(prev => [...prev, { 
                               id: Date.now().toString(), 
                               role: 'assistant', 
                               content: `📂 **已成功切换至项目：${p.name}**\n\n${p.description || ""}` 
                             }]);
                           }}
                           className={cn(
                             "p-4 bg-[#141414] border rounded-xl flex items-center justify-between group hover:border-blue-500/30 transition-all cursor-pointer",
                             projectInfo.id === p.id ? "border-blue-500" : "border-[#262626]"
                           )}
                         >
                            <div className="flex items-center gap-3">
                               <Folder className={cn("w-4 h-4", projectInfo.id === p.id ? "text-blue-500" : "text-slate-600")} />
                               <div className="flex flex-col gap-0.5">
                                 <span className={cn("text-xs transition-colors", projectInfo.id === p.id ? "text-white font-bold" : "text-slate-200")}>{p.name}</span>
                                 <span className="text-[10px] text-slate-600 truncate max-w-[140px]">{p.description}</span>
                               </div>
                            </div>
                            <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-blue-500 transition-colors" />
                         </div>
                       ))}
                    </div>
                 </motion.div>
               )}

               {showHistory && (
                 <motion.div 
                   initial={{ x: -20, opacity: 0 }}
                   animate={{ x: 0, opacity: 1 }}
                   exit={{ x: -20, opacity: 0 }}
                   className="absolute inset-0 z-40 bg-[#0F0F0F] flex flex-col"
                 >
                    <header className="px-6 py-6 border-b border-[#262626] flex items-center justify-between font-bold">
                       <div>历史版本</div>
                       <button onClick={() => setShowHistory(false)} className="p-2 hover:bg-[#1A1A1A] rounded-lg text-slate-500">
                          <Plus className="rotate-45 w-4 h-4" />
                       </button>
                    </header>
                    <div className="p-6 space-y-4">
                       {[
                         { time: '14:20', task: '堤顶高程调整' },
                         { time: '昨天 09:15', task: '断面初期设计' },
                         { time: '2024-04-10', task: '立项大纲编制' }
                       ].map((h, i) => (
                         <div key={i} className="p-4 bg-[#141414] border border-[#262626] rounded-xl flex flex-col gap-1 hover:border-blue-500/30 transition-all cursor-pointer">
                            <span className="text-[10px] text-slate-600 font-mono">{h.time}</span>
                            <span className="text-xs text-white">{h.task}</span>
                         </div>
                       ))}
                    </div>
                 </motion.div>
               )}

               {showSettings && (
                 <motion.div 
                   initial={{ x: -20, opacity: 0 }}
                   animate={{ x: 0, opacity: 1 }}
                   exit={{ x: -20, opacity: 0 }}
                   className="absolute inset-0 z-40 bg-[#0F0F0F] flex flex-col"
                 >
                    <header className="px-6 py-6 border-b border-[#262626] flex items-center justify-between">
                       <div className="font-bold">系统设置</div>
                       <button onClick={() => setShowSettings(false)} className="p-2 hover:bg-[#1A1A1A] rounded-lg text-slate-500">
                          <Plus className="rotate-45 w-4 h-4" />
                       </button>
                    </header>
                    <div className="flex-1 overflow-y-auto p-6 space-y-10 custom-scrollbar">

                       {/* AI Model Config Section */}
                       <section className="space-y-6">
                          <h3 className="text-[10px] font-bold text-slate-600 uppercase tracking-widest flex items-center gap-2">
                             <Cpu className="w-3 h-3" /> AI 引擎模型配置
                          </h3>

                          {/* 预设供应商 */}
                          <div className="space-y-3">
                             <label className="text-[10px] text-slate-500 font-medium ml-1">选择供应商</label>
                             <div className="grid grid-cols-2 gap-2">
                                {[
                                   { id: 'minimax', label: 'MiniMax', baseUrl: 'https://api.minimaxi.com/v1', model: 'MiniMax-M2.7' },
                                   { id: 'deepseek', label: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
                                   { id: 'kimi', label: 'Kimi', baseUrl: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
                                   { id: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o' },
                                   { id: 'gemini', label: 'Gemini', baseUrl: 'https://generativelanguage.googleapis.com/v1', model: 'gemini-2.0-flash' },
                                   { id: 'zhipu', label: '智谱AI', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4' },
                                ].map(p => (
                                   <button
                                     key={p.id}
                                     onClick={() => {
                                       setAiConfig({
                                          ...aiConfig,
                                          type: p.id as ModelType,
                                          modelName: p.model,
                                          baseUrl: p.baseUrl,
                                          apiKey: aiConfig.apiKey || '' // 保留现有key
                                       });
                                     }}
                                     className={cn(
                                       "flex items-center gap-2 py-2.5 px-3 rounded-xl border transition-all text-left",
                                       aiConfig.type === p.id
                                         ? "bg-blue-600/10 border-blue-600 text-white"
                                         : "bg-[#141414] border-[#262626] text-slate-400 hover:border-blue-500/30 hover:text-white"
                                     )}
                                   >
                                      <span className="text-[10px] font-bold">{p.label}</span>
                                   </button>
                                ))}
                             </div>
                          </div>

                          {/* 自定义配置 */}
                          <div className="space-y-4 pt-2 border-t border-[#262626]">
                             <div className="space-y-1.5">
                                <label className="text-[10px] text-slate-500 font-medium ml-1">API Base URL</label>
                                <input
                                   type="text"
                                   value={aiConfig.baseUrl}
                                   onChange={(e) => setAiConfig({...aiConfig, baseUrl: e.target.value, type: 'custom'})}
                                   placeholder="https://api.openai.com/v1"
                                   className="w-full bg-[#141414] border border-[#262626] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50"
                                />
                             </div>

                             <div className="space-y-1.5">
                                <label className="text-[10px] text-slate-500 font-medium ml-1">模型名称</label>
                                <input
                                   type="text"
                                   value={aiConfig.modelName}
                                   onChange={(e) => setAiConfig({...aiConfig, modelName: e.target.value})}
                                   placeholder="gpt-4o / MiniMax-M2.7 / deepseek-chat"
                                   className="w-full bg-[#141414] border border-[#262626] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-blue-500/50"
                                />
                             </div>

                             <div className="space-y-1.5">
                                <label className="text-[10px] text-slate-500 font-medium ml-1">API Key / Token</label>
                                <div className="relative">
                                   <input
                                      type={showApiKey ? "text" : "password"}
                                      value={aiConfig.apiKey}
                                      onChange={(e) => setAiConfig({...aiConfig, apiKey: e.target.value})}
                                      placeholder="sk-..."
                                      className="w-full bg-[#141414] border border-[#262626] rounded-lg px-3 py-2 pr-10 text-xs text-white outline-none focus:border-blue-500/50"
                                   />
                                   <button
                                     onClick={() => setShowApiKey(!showApiKey)}
                                     className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-white"
                                   >
                                      {showApiKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                   </button>
                                </div>
                                <p className="text-[9px] text-slate-600 mt-1 leading-relaxed">
                                   {aiConfig.type === 'gemini'
                                     ? "Gemini 使用 Google AI API Key，可从 Google AI Studio 获取"
                                     : "API密钥仅存储在本地浏览器中"}
                                </p>
                             </div>
                          </div>
                       </section>

                       {/* Vision Model Config Section */}
                       <section className="space-y-6 pt-4 border-t border-[#262626]">
                          <h3 className="text-[10px] font-bold text-slate-600 uppercase tracking-widest flex items-center gap-2">
                             <Eye className="w-3 h-3" /> 视觉模型配置（图片描述）
                          </h3>

                          <div className="space-y-3">
                             <label className="text-[10px] text-slate-500 font-medium ml-1">选择供应商</label>
                             <div className="grid grid-cols-2 gap-2">
                                {[
                                   { id: 'siliconflow', label: '硅基流动', baseUrl: 'https://api.siliconflow.cn/v1', model: 'Qwen/Qwen3-VL-32B-Instruct' },
                                   { id: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o' },
                                   { id: 'minimax', label: 'MiniMax', baseUrl: 'https://api.minimaxi.com/vl', model: 'MiniMax-VL-01' },
                                   { id: 'custom', label: '自定义', baseUrl: '', model: '' },
                                ].map(p => (
                                   <button
                                     key={p.id}
                                     onClick={() => {
                                       setVisionConfig({
                                          model: p.model,
                                          baseUrl: p.baseUrl,
                                          apiKey: visionConfig.apiKey
                                       });
                                     }}
                                     className={cn(
                                       "flex items-center gap-2 py-2.5 px-3 rounded-xl border transition-all text-left",
                                       visionConfig.baseUrl === p.baseUrl && p.id !== 'custom'
                                         ? "bg-purple-600/10 border-purple-600 text-white"
                                         : "bg-[#141414] border-[#262626] text-slate-400 hover:border-purple-500/30 hover:text-white"
                                     )}
                                   >
                                      <span className="text-[10px] font-bold">{p.label}</span>
                                   </button>
                                ))}
                             </div>
                          </div>

                          <div className="space-y-4 pt-2 border-t border-[#262626]">
                             <div className="space-y-1.5">
                                <label className="text-[10px] text-slate-500 font-medium ml-1">Vision API Base URL</label>
                                <input
                                   type="text"
                                   value={visionConfig.baseUrl}
                                   onChange={(e) => setVisionConfig({...visionConfig, baseUrl: e.target.value})}
                                   placeholder="https://api.siliconflow.cn/v1"
                                   className="w-full bg-[#141414] border border-[#262626] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-purple-500/50"
                                />
                             </div>

                             <div className="space-y-1.5">
                                <label className="text-[10px] text-slate-500 font-medium ml-1">Vision 模型名称</label>
                                <input
                                   type="text"
                                   value={visionConfig.model}
                                   onChange={(e) => setVisionConfig({...visionConfig, model: e.target.value})}
                                   placeholder="Qwen/Qwen3-VL-32B-Instruct / gpt-4o"
                                   className="w-full bg-[#141414] border border-[#262626] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-purple-500/50"
                                />
                                <p className="text-[9px] text-slate-600 mt-1 leading-relaxed">
                                   用于生成PDF图片的语义描述，需支持多模态视觉识别
                                </p>
                             </div>

                             <div className="space-y-1.5">
                                <label className="text-[10px] text-slate-500 font-medium ml-1">Vision API Key</label>
                                <div className="relative">
                                   <input
                                      type={showVisionApiKey ? "text" : "password"}
                                      value={visionConfig.apiKey}
                                      onChange={(e) => setVisionConfig({...visionConfig, apiKey: e.target.value})}
                                      placeholder="sk-...（留空则使用 LLM API Key）"
                                      className="w-full bg-[#141414] border border-[#262626] rounded-lg px-3 py-2 pr-10 text-xs text-white outline-none focus:border-purple-500/50"
                                   />
                                   <button
                                     onClick={() => setShowVisionApiKey(!showVisionApiKey)}
                                     className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-white"
                                   >
                                      {showVisionApiKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                   </button>
                                </div>
                                <p className="text-[9px] text-slate-600 mt-1 leading-relaxed">
                                   硅基流动免费额度注册：cloud.siliconflow.cn
                                </p>
                             </div>
                          </div>
                       </section>

                       {/* Embedding Model Config Section */}
                       <section className="space-y-6 pt-4 border-t border-[#262626]">
                          <h3 className="text-[10px] font-bold text-slate-600 uppercase tracking-widest flex items-center gap-2">
                             <Database className="w-3 h-3" /> Embedding 向量模型配置
                          </h3>

                          <div className="space-y-3">
                             <label className="text-[10px] text-slate-500 font-medium ml-1">选择供应商</label>
                             <div className="grid grid-cols-2 gap-2">
                                {[
                                   { id: 'siliconflow', label: '硅基流动', baseUrl: 'https://api.siliconflow.cn/v1', model: 'BAAI/bge-large-zh-v1.5' },
                                   { id: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: 'text-embedding-3-small' },
                                   { id: 'minimax', label: 'MiniMax', baseUrl: 'https://api.minimaxi.com/v1', model: 'embo-01' },
                                   { id: 'custom', label: '自定义', baseUrl: '', model: '' },
                                ].map(p => (
                                   <button
                                     key={p.id}
                                     onClick={() => {
                                       setEmbeddingConfig({
                                          model: p.model,
                                          baseUrl: p.baseUrl,
                                          apiKey: embeddingConfig.apiKey
                                       });
                                     }}
                                     className={cn(
                                       "flex items-center gap-2 py-2.5 px-3 rounded-xl border transition-all text-left",
                                       embeddingConfig.baseUrl === p.baseUrl && p.id !== 'custom'
                                         ? "bg-emerald-600/10 border-emerald-600 text-white"
                                         : "bg-[#141414] border-[#262626] text-slate-400 hover:border-emerald-500/30 hover:text-white"
                                     )}
                                   >
                                      <span className="text-[10px] font-bold">{p.label}</span>
                                   </button>
                                ))}
                             </div>
                          </div>

                          <div className="space-y-4 pt-2 border-t border-[#262626]">
                             <div className="space-y-1.5">
                                <label className="text-[10px] text-slate-500 font-medium ml-1">Embedding API Base URL</label>
                                <input
                                   type="text"
                                   value={embeddingConfig.baseUrl}
                                   onChange={(e) => setEmbeddingConfig({...embeddingConfig, baseUrl: e.target.value})}
                                   placeholder="https://api.siliconflow.cn/v1"
                                   className="w-full bg-[#141414] border border-[#262626] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-emerald-500/50"
                                />
                             </div>

                             <div className="space-y-1.5">
                                <label className="text-[10px] text-slate-500 font-medium ml-1">Embedding 模型名称</label>
                                <input
                                   type="text"
                                   value={embeddingConfig.model}
                                   onChange={(e) => setEmbeddingConfig({...embeddingConfig, model: e.target.value})}
                                   placeholder="BAAI/bge-large-zh-v1.5"
                                   className="w-full bg-[#141414] border border-[#262626] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-emerald-500/50"
                                />
                                <p className="text-[9px] text-slate-600 mt-1 leading-relaxed">
                                   推荐使用硅基流动的 BAAI/bge-large-zh-v1.5（中文优化），DeepSeek 不支持 Embedding
                                </p>
                             </div>

                             <div className="space-y-1.5">
                                <label className="text-[10px] text-slate-500 font-medium ml-1">Embedding API Key</label>
                                <div className="relative">
                                   <input
                                      type={showEmbeddingApiKey ? "text" : "password"}
                                      value={embeddingConfig.apiKey}
                                      onChange={(e) => setEmbeddingConfig({...embeddingConfig, apiKey: e.target.value})}
                                      placeholder="sk-...（留空则使用 LLM API Key）"
                                      className="w-full bg-[#141414] border border-[#262626] rounded-lg px-3 py-2 pr-10 text-xs text-white outline-none focus:border-emerald-500/50"
                                   />
                                   <button
                                     onClick={() => setShowEmbeddingApiKey(!showEmbeddingApiKey)}
                                     className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-white"
                                   >
                                      {showEmbeddingApiKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                   </button>
                                </div>
                             </div>
                          </div>
                       </section>

                       <section className="space-y-4 pt-4 border-t border-[#262626]">
                          <h3 className="text-[10px] font-bold text-slate-600 uppercase tracking-widest flex items-center gap-2">
                             <Lock className="w-3 h-3" /> 用户信息与权限
                          </h3>
                          <div className="p-4 bg-[#141414] rounded-xl border border-[#262626] space-y-4">
                             <div className="flex items-center gap-4">
                                <div className="w-10 h-10 rounded-full bg-blue-600/10 border border-blue-500/30 flex items-center justify-center text-xs font-bold text-blue-500">
                                  {userProfile.avatar_initial || '张'}
                                </div>
                                <div className="flex-1 space-y-1">
                                   <p className="text-xs font-bold text-white">{userProfile.name}</p>
                                   <p className="text-[10px] text-slate-600">{userProfile.email}</p>
                                </div>
                             </div>
                             <div className="space-y-3">
                                <div>
                                   <label className="text-[10px] text-slate-500 mb-1 block">姓名</label>
                                   <input
                                     type="text"
                                     value={userProfile.name}
                                     onChange={e => setUserProfile(prev => ({ ...prev, name: e.target.value }))}
                                     className="w-full bg-[#0A0A0A] border border-[#262626] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                                     placeholder="姓名"
                                   />
                                </div>
                                <div>
                                   <label className="text-[10px] text-slate-500 mb-1 block">邮箱</label>
                                   <input
                                     type="email"
                                     value={userProfile.email}
                                     onChange={e => setUserProfile(prev => ({ ...prev, email: e.target.value }))}
                                     className="w-full bg-[#0A0A0A] border border-[#262626] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                                     placeholder="email@example.com"
                                   />
                                </div>
                                <div>
                                   <label className="text-[10px] text-slate-500 mb-1 block">头像字母</label>
                                   <input
                                     type="text"
                                     maxLength={1}
                                     value={userProfile.avatar_initial}
                                     onChange={e => setUserProfile(prev => ({ ...prev, avatar_initial: e.target.value || '张' }))}
                                     className="w-full bg-[#0A0A0A] border border-[#262626] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                                     placeholder="张"
                                   />
                                </div>
                             </div>
                          </div>
                       </section>
                    </div>
                    <div className="p-6 border-t border-[#262626]">
                       <button
                        onClick={async () => {
                          try { localStorage.setItem('aiConfig', JSON.stringify(aiConfig)); } catch (e) {}
                          try { localStorage.setItem('embeddingConfig', JSON.stringify(embeddingConfig)); } catch (e) {}
                          try { localStorage.setItem('visionConfig', JSON.stringify(visionConfig)); } catch (e) {}
                          // Sync user profile to backend
                          try {
                            await fetch('/api/user/profile', {
                              method: 'PUT',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({
                                name: userProfile.name,
                                email: userProfile.email,
                                avatar_initial: userProfile.avatar_initial,
                              }),
                            });
                          } catch (e) {}
                          setShowSettings(false);
                          const visionInfo = visionConfig.model ? ` | 视觉: ${visionConfig.model}` : '';
                          setMessages(prev => [...prev, { id: Date.now().toString(), role: 'assistant', content: `✅ 配置已保存：[${aiConfig.type}] ${aiConfig.modelName}${visionInfo}` }]);
                        }}
                        className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-blue-600/20"
                       >
                          保存并应用
                       </button>
                    </div>
                 </motion.div>
               )}
            </AnimatePresence>

            <header className="px-6 py-4 border-b border-[#262626] space-y-4">
               <div className="flex items-center justify-between">
                  <h2 className="text-xs font-semibold text-white uppercase tracking-widest opacity-50">专业能力模块</h2>
                  <button 
                    onClick={() => {
                      setMessages([{ id: Date.now().toString(), role: 'assistant', content: '✨ 已为您开启全新设计篇章。请告知我您的新设计需求，或上传相关规范文件。' }]);
                      setSystemStatus('idle');
                    }}
                    className="p-1 px-2 border border-[#262626] rounded text-[10px] text-slate-500 hover:text-blue-400 hover:border-blue-500/30 transition-all flex items-center gap-1.5"
                  >
                    <Plus className="w-3 h-3" /> 新篇章
                  </button>
               </div>
               
               {/* 3 Core Departments Nav */}
               <nav className="flex bg-[#0D0D0D] p-1 rounded-xl border border-[#262626]">
                  {[
                    { id: 'consulting', label: '水务咨询' },
                    { id: 'river', label: '河道设计' },
                    { id: 'drainage', label: '给排水' },
                  ].map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => setCurrentCategory(cat.id as Category)}
                      className={cn(
                        "flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all",
                        currentCategory === cat.id 
                          ? "bg-[#1A1A1A] text-blue-500 shadow-sm" 
                          : "text-slate-500 hover:text-slate-300"
                      )}
                    >
                      {cat.label}
                    </button>
                  ))}
               </nav>
            </header>

            <div className="flex-1 min-h-0 overflow-y-auto px-6 py-8 space-y-8 custom-scrollbar">
               {messages.map((msg) => (
                 <div key={msg.id} className={cn("flex flex-col gap-2", msg.role === 'user' ? "items-end" : "items-start")}>
                    <div className={cn(
                      "group relative",
                      msg.role === 'user' ? "chat-bubble-user" : "chat-bubble-ai"
                    )}>
                       <div className="text-white prose prose-invert prose-sm max-w-none [&_img]:max-w-full [&_img]:rounded-lg [&_img]:my-2 [&_img]:border [&_img]:border-[#262626]">
                         <Markdown>{msg.content}</Markdown>
                       </div>
                    </div>
                    <span className="text-[10px] text-slate-600 font-medium px-2 uppercase tracking-tighter">
                       {msg.role === 'user' ? 'GUEST' : 'WATERDESIGN AI'}
                    </span>
                 </div>
               ))}
               {isLoading && (
                 <div className="flex items-center gap-3 animate-pulse">
                    <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                    <span className="text-xs text-slate-500">Processing...</span>
                 </div>
               )}
               <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-6 border-t border-[#262626] bg-[#0F0F0F] shrink-0">
               <div className="relative group">
                  <textarea 
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handleSend())}
                    placeholder="Ask AI to design, analyze or draft..."
                    rows={3}
                    className="w-full bg-[#1A1A1A] border border-[#262626] rounded-2xl px-5 py-4 outline-none focus:border-blue-500/50 text-[13px] leading-relaxed transition-all resize-none placeholder:text-slate-600 shadow-inner"
                  />
                  <div className="absolute right-4 bottom-4 flex items-center gap-2">
                     <span className="text-[10px] text-slate-600 font-mono">⌘ + ↵</span>
                     <button 
                       onClick={handleSend}
                       className={cn(
                         "p-2 rounded-xl transition-all shadow-xl",
                         chatInput.trim() ? "bg-blue-600 text-white shadow-blue-600/20" : "bg-[#262626] text-slate-600"
                       )}
                     >
                       <ArrowRight className="w-4 h-4" />
                     </button>
                  </div>
               </div>
               <div className="flex gap-2 mt-4 px-2 overflow-x-auto no-scrollbar">
                  {['堤顶高程规范', '河道横断面绘制', '编制设计大纲'].map(t => (
                    <button key={t} className="whitespace-nowrap px-3 py-1.5 rounded-lg border border-[#262626] text-[10px] font-medium text-slate-500 hover:text-slate-200 hover:border-blue-500/30 transition-all bg-[#141414]">
                      {t}
                    </button>
                  ))}
               </div>
            </div>
          </div>
         </section>

       {/* Right: The Artifact Display (Large Stage) */}
       <AnimatePresence>
          {viewMode === 'workspace' && (
             <motion.section 
               initial={{ x: 100, opacity: 0 }}
               animate={{ x: 0, opacity: 1 }}
               exit={{ x: 100, opacity: 0 }}
               transition={{ type: 'spring', damping: 25, stiffness: 200 }}
               className="flex-1 bg-[#0a0a0a] flex flex-col overflow-hidden relative border-l border-[#262626] h-full"
             >
            <div className="absolute inset-0 blueprint-grid opacity-20 pointer-events-none" />
            
            {/* Artifact Toolbar */}
            <header className="h-14 border-b border-[#262626] bg-[#0D0D0D]/50 backdrop-blur-md flex items-center justify-between px-8 z-10">
               <div className="flex items-center gap-8">
                  <div className="flex items-center gap-3">
                     <div className="p-1.5 bg-blue-600/10 rounded-lg">
                        <FileText className="w-4 h-4 text-blue-500" />
                     </div>
                     <span className="text-[13px] font-semibold text-white">
                        {projectInfo.name || "未命名工程"}
                     </span>
                  </div>
                  <nav className="flex gap-1">
                     {['报告预览', 'CAD模式', '结构核算'].map((tab, i) => (
                       <button 
                        key={tab} 
                        onClick={() => setActiveArtifact(i === 0 ? 'report' : i === 1 ? 'drawing' : 'analysis')}
                        className={cn(
                          "px-4 py-1.5 rounded-lg text-xs font-medium transition-all",
                          ((activeArtifact === 'report' && i === 0) || (activeArtifact === 'drawing' && i === 1) || (activeArtifact === 'analysis' && i === 2))
                            ? "bg-[#1A1A1A] text-blue-500" 
                            : "text-slate-500 hover:text-slate-300"
                        )}
                       >
                         {tab}
                       </button>
                     ))}
                  </nav>
               </div>
               <div className="flex items-center gap-3">
                  <button 
                    onClick={() => {
                       let filename = "";
                       let mimeType = "";
                       let content = "";
                       let typeLabel = "";

                       setSystemStatus('export');

                       if (activeArtifact === 'report') {
                          filename = `WaterDesign_Report_${Date.now()}.docx`;
                          mimeType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
                          content = "Mock Word content: " + JSON.stringify({ project: currentCategory, messages, params });
                          typeLabel = "Word 报告文档 (.docx)";
                       } else if (activeArtifact === 'drawing') {
                          filename = `WaterDesign_CAD_${Date.now()}.dxf`;
                          mimeType = "application/dxf";
                          content = "999\nDXF Mock Content\n0\nSECTION\n2\nENTITIES\n0\nLINE\n10\n0.0\n20\n0.0\n30\n0.0\n11\n100.0\n21\n100.0\n31\n0.0\n0\nENDSEC\n0\nEOF";
                          typeLabel = "DXF 矢量图纸 (.dxf)";
                       } else {
                          filename = `WaterDesign_Analysis_${Date.now()}.xlsx`;
                          mimeType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
                          content = "Mock Excel content: " + JSON.stringify(params);
                          typeLabel = "Excel 核算清单 (.xlsx)";
                       }

                       // Trigger download
                       const blob = new Blob([content], { type: mimeType });
                       const url = URL.createObjectURL(blob);
                       const a = document.createElement('a');
                       a.href = url;
                       a.download = filename;
                       document.body.appendChild(a);
                       a.click();
                       document.body.removeChild(a);
                       URL.revokeObjectURL(url);

                       setTimeout(() => {
                          setSystemStatus('idle');
                          setMessages(prev => [...prev, { 
                             id: Date.now().toString(), 
                             role: 'assistant', 
                             content: `✅ 导出成功！文件已保存为 **${filename}**。\n\n已根据当前模式为您匹配最佳格式：\n- **导出类型**: ${typeLabel}\n- **工程节点**: ${currentCategory}` 
                          }]);
                       }, 1000);
                    }}
                    className="flex items-center gap-2 px-3 py-1.5 bg-[#1A1A1A] border border-[#262626] rounded-lg text-xs font-medium hover:bg-[#262626] hover:text-blue-400 transition-all"
                  >
                     <Download className="w-3.5 h-3.5" /> 导出
                  </button>
               </div>
            </header>

            {/* Artifact Content Area */}
            <div className="flex-1 overflow-y-auto p-12 custom-scrollbar z-10 relative">
               
               {/* System Status Float */}
               <div className="absolute top-6 left-1/2 -translate-x-1/2 z-30">
                  <AnimatePresence>
                     {systemStatus !== 'idle' && (
                        <motion.div 
                          initial={{ y: -20, opacity: 0 }}
                          animate={{ y: 0, opacity: 1 }}
                          exit={{ y: -20, opacity: 0 }}
                          className="px-4 py-2 bg-blue-600 rounded-full shadow-2xl flex items-center gap-3 border border-blue-400/30"
                        >
                           <RefreshCw className="w-3.5 h-3.5 text-white animate-spin" />
                           <span className="text-[10px] font-bold text-white uppercase tracking-widest leading-none">
                              {systemStatus === 'hydraulic' && "Hydraulic Solver Active"}
                              {systemStatus === 'cad' && "CAD Engine Syncing..."}
                              {systemStatus === 'export' && "Data Extracting..."}
                           </span>
                        </motion.div>
                     )}
                  </AnimatePresence>
               </div>

               <AnimatePresence mode="wait">
                  {activeArtifact === 'report' && (
                    <motion.div 
                      key="report"
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -20 }}
                      className="max-w-[850px] mx-auto artifact-stage p-16 min-h-[1100px]"
                    >
                        <div className="space-y-12 leading-loose text-slate-300">
                           <div className="text-center space-y-4 pb-12 border-b border-[#262626]">
                              <h1 className="text-3xl font-bold text-white tracking-tight">
                                {currentCategory === 'consulting' && "水务咨询项目技术报告"}
                                {currentCategory === 'river' && "河道整治工程设计方案"}
                                {currentCategory === 'drainage' && "市政给排水管网设计说明"}
                              </h1>
                              <p className="text-slate-500 font-mono text-[11px] uppercase tracking-widest">
                                {currentCategory === 'consulting' && "Water Resources Consulting & Evaluation"}
                                {currentCategory === 'river' && "Hydraulic Engineering AI Design Report"}
                                {currentCategory === 'drainage' && "Pipe Network & Urban Drainage Systems"}
                              </p>
                           </div>

                           <section className="space-y-6">
                              <h2 className="text-lg font-bold text-blue-500 flex items-center gap-3">
                                <span className="w-8 h-8 rounded-lg bg-blue-600/10 flex items-center justify-center text-[11px] font-mono">01</span>
                                {currentCategory === 'consulting' ? "项目背景与资源评估" : "工程概况与地质特征"}
                              </h2>
                              <div className="space-y-4 text-[14px]">
                                 <p className="indent-8 text-justify">
                                    {currentCategory === 'consulting' && "根据当地社会经济发展规划及水资源开发利用现状，本咨询报告旨在对区域供水保障程度及水环境承载能力进行深度解析。"}
                                    {currentCategory === 'river' && "本项目位于区域一级支流，治理段长度约 3.5km。由于两岸堤防标准偏低，防洪排涝能力不足，急需进行提标加固。"}
                                    {currentCategory === 'drainage' && "结合海绵城市设计要求，本次给排水系统方案重点关注地块径流系数控制、雨污水管网的分流制系统布局。"}
                                 </p>
                                 <div className="grid grid-cols-2 gap-4">
                                    <div className="p-4 bg-[#1A1A1A] border border-[#262626] rounded-xl space-y-2">
                                       <span className="text-[10px] text-slate-600 font-bold uppercase tracking-wider">
                                          {currentCategory === 'consulting' ? "年需水量预测" : (currentCategory === 'drainage' ? "污水收集率" : "设计流量")}
                                       </span>
                                       <p className="text-base font-mono text-white">
                                          {currentCategory === 'consulting' ? "1,240 万 m³" : (currentCategory === 'drainage' ? "100%" : "5,230 m³/s")}
                                       </p>
                                    </div>
                                    <div className="p-4 bg-[#1A1A1A] border border-[#262626] rounded-xl space-y-2">
                                       <span className="text-[10px] text-slate-600 font-bold uppercase tracking-wider">
                                          {currentCategory === 'drainage' ? "重现期" : "计算标准"}
                                       </span>
                                       <p className="text-base font-mono text-white">
                                          {currentCategory === 'drainage' ? "P=50 (2%)" : (currentCategory === 'consulting' ? "SL 235-1999" : "GB 50286-2024")}
                                       </p>
                                    </div>
                                 </div>
                              </div>
                           </section>

                           <section className="space-y-6 pt-6">
                              <h2 className="text-lg font-bold text-blue-500 flex items-center gap-3">
                                <span className="w-8 h-8 rounded-lg bg-blue-600/10 flex items-center justify-center text-[11px] font-mono">02</span>
                                断面设计参数核算 (GB50286)
                              </h2>
                              <div className="p-8 border border-amber-500/20 bg-amber-500/5 rounded-2xl relative overflow-hidden group">
                                 <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl pointer-events-none" />
                                 <h4 className="text-xs font-bold text-amber-500 mb-4 flex items-center gap-2">
                                    <AlertCircle className="w-3.5 h-3.5" /> 规范检核结论
                                 </h4>
                                 <p className="text-sm text-slate-400 italic">
                                    "根据堤防工程级别及防洪余地要求，当前设计的堤顶高程稍低于规范限值。AI 建议将受风力影响严重的 K2+300 段附加 0.45m 的防浪墙高度。"
                                 </p>
                              </div>
                           </section>
                        </div>
                    </motion.div>
                  )}

                  {activeArtifact === 'drawing' && (
                    <motion.div 
                      key="drawing"
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      className="max-w-[1000px] mx-auto artifact-stage aspect-[16/10] bg-[#000] p-0 overflow-hidden relative"
                    >
                       <div className="h-full w-full flex flex-col">
                          <header className="p-4 border-b border-[#262626] flex items-center justify-between bg-[#0F0F0F]">
                             <span className="text-[10px] font-bold text-slate-400 flex items-center gap-2">
                                <Ruler className="w-3 h-3" /> CAD PREVIEW: SECTION_Typical.dwg
                             </span>
                             <div className="flex gap-4 text-[9px] font-mono text-slate-600">
                                <span>X: 142.554</span>
                                <span>Y: 89.213</span>
                                <span className="text-emerald-500 flex items-center gap-1">
                                   <Zap className="w-2.5 h-2.5" /> LIVE SYNC
                                </span>
                             </div>
                          </header>
                          <div className="flex-1 relative bg-[#0a0a0a]">
                             <div className="absolute inset-0 blueprint-grid opacity-30" />
                             <svg viewBox="0 0 800 400" className="w-full h-full p-20 overflow-visible drop-shadow-2xl">
                                {/* Ground Line */}
                                <path 
                                  d="M 50 350 Q 200 350, 250 320 L 550 320 Q 600 350, 750 350" 
                                  stroke="#333" 
                                  strokeWidth="1.5" 
                                  fill="none" 
                                  strokeDasharray="5,5" 
                                />
                                {/* Main Structure */}
                                <motion.path 
                                  d="M 220 350 L 280 220 L 520 220 L 580 350" 
                                  stroke="#3b82f6" 
                                  strokeWidth="2" 
                                  fill="rgba(59, 130, 246, 0.08)"
                                  initial={{ pathLength: 0 }}
                                  animate={{ pathLength: 1 }}
                                  transition={{ duration: 2 }}
                                />
                                
                                {/* Interactive CAD Label */}
                                <g className="cursor-pointer group" onClick={() => setShowParams(true)}>
                                   <text x="380" y="190" className="text-[9px] fill-blue-500 font-mono font-bold group-hover:fill-blue-400 transition-colors">B = 6.0m</text>
                                   <line x1="280" y1="200" x2="520" y2="200" stroke="#3b82f6" strokeWidth="1" strokeDasharray="2,2" />
                                   <circle cx="280" cy="200" r="2" fill="#3b82f6" />
                                   <circle cx="520" cy="200" r="2" fill="#3b82f6" />
                                </g>

                                {/* Static Labels */}
                                <text x="290" y="210" className="text-[10px] fill-blue-400 font-mono italic">K+120 断面设计</text>
                             </svg>
                          </div>
                       </div>
                    </motion.div>
                  )}
               </AnimatePresence>

               {/* Right Side: Properties Panel Float */}
               <AnimatePresence>
                  {showParams && (
                     <motion.div 
                       initial={{ x: 20, opacity: 0 }}
                       animate={{ x: 0, opacity: 1 }}
                       exit={{ x: 20, opacity: 0 }}
                       className="absolute right-6 top-24 w-64 bg-[#141414] border border-[#262626] rounded-2xl shadow-3xl z-40 overflow-hidden"
                     >
                        <header className="px-4 py-3 border-b border-[#262626] flex items-center justify-between bg-[#1A1A1A]">
                           <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">参数精控台</span>
                           <button onClick={() => setShowParams(false)} className="text-slate-600 hover:text-white transition-colors">
                              <Plus className="rotate-45 w-3.5 h-3.5" />
                           </button>
                        </header>
                        <div className="p-4 space-y-4">
                           {params.map((p, idx) => (
                             <div key={p.id} className="space-y-1.5">
                                <label className="text-[10px] text-slate-500 font-medium">{p.label}</label>
                                <div className="flex gap-2">
                                   <input 
                                     type="text" 
                                     value={p.value} 
                                     onChange={(e) => {
                                       const newParams = [...params];
                                       newParams[idx].value = e.target.value;
                                       setParams(newParams);
                                     }}
                                     className="flex-1 bg-[#0D0D0D] border border-[#262626] rounded-lg px-2 py-1.5 text-xs text-blue-400 outline-none focus:border-blue-500/50"
                                   />
                                   {p.unit && <span className="text-[10px] text-slate-700 flex items-center">{p.unit}</span>}
                                </div>
                             </div>
                           ))}
                           <button onClick={handleSyncParams} className="w-full py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-[10px] font-bold text-white transition-all shadow-lg shadow-blue-600/10 flex items-center justify-center gap-2">
                              <RefreshCw className="w-3 h-3" /> 同步至 AI 引擎
                           </button>
                        </div>
                     </motion.div>
                  )}
               </AnimatePresence>
            </div>

            {/* Stage Controls */}
            <div className="absolute bottom-8 right-8 z-20 flex gap-2">
               <button onClick={() => handleSyncParams()} className="px-4 py-2 bg-blue-600 rounded-xl text-white text-xs font-bold shadow-2xl shadow-blue-600/30 flex items-center gap-2">
                 <Terminal className="w-3.5 h-3.5" /> 重新计算
               </button>
               <button onClick={() => setShowHistory(true)} className="px-4 py-2 bg-[#1A1A1A] border border-[#262626] rounded-xl text-xs font-bold hover:bg-[#262626] transition-all">
                 锁定方案
               </button>
            </div>
          </motion.section>
       )}
    </AnimatePresence>
 </div>

      {/* Project Setup Modal Overlay */}
      <AnimatePresence>
        {showNewProjectModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
             <motion.div 
               initial={{ opacity: 0 }}
               animate={{ opacity: 1 }}
               exit={{ opacity: 0 }}
               className="absolute inset-0 bg-black/60 backdrop-blur-sm"
               onClick={() => setShowNewProjectModal(false)}
             />
             <motion.div 
               initial={{ scale: 0.95, opacity: 0, y: 20 }}
               animate={{ scale: 1, opacity: 1, y: 0 }}
               exit={{ scale: 0.95, opacity: 0, y: 20 }}
               className="relative w-full max-w-md bg-[#0D0D0D] border border-[#262626] rounded-2xl p-8 shadow-2xl overflow-hidden"
             >
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 to-orange-500" />
                
                <div className="flex items-center gap-4 mb-6">
                   <div className="p-3 bg-blue-600/10 rounded-xl">
                      <Plus className="w-6 h-6 text-blue-500" />
                   </div>
                   <div>
                      <h2 className="text-xl font-bold text-white">启动新水利项目</h2>
                      <p className="text-xs text-slate-500 mt-1">请填写项目基本信息以初始化 AI 设计环境</p>
                   </div>
                </div>

                <div className="space-y-5">
                   <div className="space-y-2">
                      <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">项目类型</label>
                      <div className="grid grid-cols-3 gap-2">
                         {[
                            { id: 'consulting', label: '水务咨询', desc: '规划/论证' },
                            { id: 'river', label: '河道设计', desc: '整治/堤防' },
                            { id: 'drainage', label: '给排水', desc: '管网/海绵' }
                         ].map(cat => (
                            <button
                              key={cat.id}
                              onClick={() => setNewProjectCategory(cat.id as Category)}
                              className={cn(
                                "p-3 rounded-xl border transition-all text-center",
                                newProjectCategory === cat.id
                                  ? "bg-blue-600/10 border-blue-600 text-white"
                                  : "bg-[#141414] border-[#262626] text-slate-400 hover:border-blue-500/30"
                              )}
                            >
                               <div className="text-xs font-bold">{cat.label}</div>
                               <div className="text-[9px] text-slate-600 mt-0.5">{cat.desc}</div>
                            </button>
                         ))}
                      </div>
                   </div>

                   <div className="space-y-2">
                      <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">项目名称</label>
                      <input
                        type="text"
                        placeholder="例如：XX河道生态整治工程"
                        className="w-full h-12 bg-[#1A1A1A] border border-[#262626] rounded-xl px-4 text-sm text-white focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/10 transition-all font-sans"
                        id="newProjectName"
                      />
                   </div>
                   <div className="space-y-2">
                      <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">项目简介 (可选)</label>
                      <textarea
                        placeholder="简述工程背景、设计目标或特殊工况..."
                        rows={3}
                        className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl p-4 text-sm text-white focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/10 transition-all resize-none font-sans"
                        id="newProjectDesc"
                      />
                   </div>
                </div>

                <div className="flex gap-3 mt-8">
                   <button 
                     onClick={() => setShowNewProjectModal(false)}
                     className="flex-1 h-11 border border-[#262626] text-slate-400 text-sm font-medium rounded-xl hover:bg-[#1A1A1A] transition-all"
                   >
                      取消
                   </button>
                   <button
                     onClick={() => {
                       const nameElem = document.getElementById('newProjectName') as HTMLInputElement;
                       const descElem = document.getElementById('newProjectDesc') as HTMLTextAreaElement;
                       const name = nameElem?.value || "未命名工程";
                       const desc = descElem?.value || "";

                       const categoryLabels = { consulting: '水务咨询', river: '河道设计', drainage: '给排水' };
                       const newProj = {
                         id: Date.now().toString(),
                         name,
                         description: desc,
                         category: newProjectCategory
                       };

                       setProjects(prev => [newProj, ...prev]);
                       setProjectInfo(newProj);
                       setCurrentCategory(newProjectCategory);
                       setSystemStatus('export');

                       setTimeout(() => {
                          setMessages([{
                             id: Date.now().toString(),
                             role: 'assistant',
                             content: `🚀 **项目 "${name}" 已成功创建**（${categoryLabels[newProjectCategory]}）。\n\n**项目背景**：${desc || "未提供"}\n\n所有设计模块现已关联至该项目。您可以开始下达指令。`
                          }]);
                          setSystemStatus('idle');
                          setActiveArtifact('none');
                          setShowNewProjectModal(false);
                       }, 600);
                     }}
                     className="flex-[2] h-11 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded-xl shadow-lg shadow-blue-600/10 transition-all active:scale-95"
                   >
                      创建项目
                   </button>
                </div>
             </motion.div>
          </div>
        )}
      </AnimatePresence>

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #262626; border-radius: 4px; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
      `}</style>
    </div>
  );
}
