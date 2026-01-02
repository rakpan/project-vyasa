//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
"use client"

import React, { useState, useEffect } from "react"
import { 
  Settings, 
  Database, 
  Save, 
  Eye,
  EyeOff,
  Search as SearchIcon,
  Cpu,
  Server,
  RefreshCw,
  Check,
  X
} from "lucide-react"
import { GraphDBType } from "@/lib/graph-db-service"
import { useToast } from "@/hooks/use-toast"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export function SettingsModal() {
  const { toast } = useToast()
  const [isOpen, setIsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState("models")
  const [showPassword, setShowPassword] = useState(false)
  
  // Graph DB settings
  const [graphDbType] = useState<GraphDBType>("arangodb")
  const [arangoUrl, setArangoUrl] = useState("http://localhost:8529")
  const [arangoDb, setArangoDb] = useState("project_vyasa")
  const [arangoUser, setArangoUser] = useState("")
  const [arangoPassword, setArangoPassword] = useState("")
  
  // Vector DB settings - Qdrant (local vector database)
  // Note: These are kept for backward compatibility but Qdrant doesn't use API keys
  const [qdrantApiKey, setQdrantApiKey] = useState("")
  const [qdrantEnvironment, setQdrantEnvironment] = useState("")
  const [qdrantIndex, setQdrantIndex] = useState("")
  
  // Embeddings model settings
  const [embeddingsProvider, setEmbeddingsProvider] = useState("local")
  const [nvidiaEmbeddingsModel, setNvidiaEmbeddingsModel] = useState("nvidia/llama-3.2-nv-embedqa-1b-v2")
  
  // Ollama model configuration
  const [availableOllamaModels, setAvailableOllamaModels] = useState<string[]>([])
  const [selectedOllamaModels, setSelectedOllamaModels] = useState<string[]>([])
  const [isLoadingOllamaModels, setIsLoadingOllamaModels] = useState(false)
  const [ollamaConnectionStatus, setOllamaConnectionStatus] = useState<'idle' | 'connected' | 'error'>('idle')
  const [ollamaError, setOllamaError] = useState<string | null>(null)
  
  // Listen for open-settings event
  useEffect(() => {
    const handleOpenSettings = (event: CustomEvent) => {
      const { tab } = event.detail
      setIsOpen(true)
      if (tab) {
        setActiveTab(tab)
      }
    }
    
    window.addEventListener('open-settings', handleOpenSettings as EventListener)
    
    return () => {
      window.removeEventListener('open-settings', handleOpenSettings as EventListener)
    }
  }, [])
  
  // Automatically fetch Ollama models when modal opens and models tab is active
  useEffect(() => {
    if (isOpen && activeTab === "models" && ollamaConnectionStatus === 'idle') {
      fetchOllamaModels()
    }
  }, [isOpen, activeTab])
  
  // Load settings from server/env when modal opens (no localStorage use)
  useEffect(() => {
    if (!isOpen) return
    const hydrate = async () => {
      try {
        const resp = await fetch("/api/settings")
        const data = await resp.json()
        const settings = data.settings || {}
        setEmbeddingsProvider(settings.embeddings_provider || process.env.NEXT_PUBLIC_EMBEDDINGS_PROVIDER || "local")
        setNvidiaEmbeddingsModel(
          settings.nvidia_embeddings_model || process.env.NEXT_PUBLIC_NVIDIA_EMBEDDINGS_MODEL || "nvidia/llama-3.2-nv-embedqa-1b-v2"
        )
        
        if (Array.isArray(settings.selected_ollama_models)) {
          setSelectedOllamaModels(settings.selected_ollama_models)
        }
        
        setArangoUrl(settings.arango_url || process.env.NEXT_PUBLIC_ARANGO_URL || "http://localhost:8529")
        setArangoDb(settings.arango_db || process.env.NEXT_PUBLIC_ARANGO_DB || "project_vyasa")
        setArangoUser(settings.arango_user || process.env.NEXT_PUBLIC_ARANGO_USER || "")
        setArangoPassword("") // never expose secrets
        
        setQdrantApiKey("") // Qdrant does not require API key in local mode
        setQdrantEnvironment(settings.qdrant_environment || "")
        setQdrantIndex(settings.qdrant_collection || "")
      } catch (err) {
        console.error("Failed to load settings from server", err)
      }
    }
    hydrate()
  }, [isOpen])
  
  // Save database settings
  const saveDbSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Sync settings with server
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          settings: {
            graph_db_type: graphDbType,
            arango_url: arangoUrl,
            arango_db: arangoDb,
            arango_user: arangoUser,
            arango_password: arangoPassword
          }
        }),
      });
    } catch (error) {
      console.error('Error syncing settings:', error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to sync settings with server"
      });
    }
    
    toast({
      title: "Success",
      description: "Graph database settings saved"
    });
    setIsOpen(false)
  }
  
  // Save vector database settings
  const saveVectorDbSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Sync settings with server
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          settings: {
            qdrant_api_key: qdrantApiKey,
            qdrant_environment: qdrantEnvironment,
            qdrant_collection: qdrantIndex,
          }
        }),
      });
    } catch (error) {
      console.error('Error syncing settings:', error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to sync settings with server"
      });
    }
    
    toast({
      title: "Success",
      description: "Vector database settings saved"
    })
  }
  
  // Fetch available Ollama models
  const fetchOllamaModels = async () => {
    setIsLoadingOllamaModels(true)
    setOllamaError(null)
    
    try {
      const response = await fetch('/api/ollama?action=test-connection')
      const data = await response.json()
      
      if (data.connected && data.models) {
        setAvailableOllamaModels(data.models)
        setOllamaConnectionStatus('connected')
        
        // If no models are selected yet, select all by default
        if (selectedOllamaModels.length === 0) {
          setSelectedOllamaModels(data.models)
        }
      } else {
        setOllamaConnectionStatus('error')
        setOllamaError(data.error || 'Failed to connect to Ollama')
        setAvailableOllamaModels([])
      }
    } catch (error) {
      console.error('Error fetching Ollama models:', error)
      setOllamaConnectionStatus('error')
      setOllamaError(error instanceof Error ? error.message : 'Unknown error')
      setAvailableOllamaModels([])
    } finally {
      setIsLoadingOllamaModels(false)
    }
  }

  // Save Ollama model settings
  const saveOllamaSettings = (e: React.FormEvent) => {
    e.preventDefault()
    
    // Save selected models to localStorage
    localStorage.setItem("selected_ollama_models", JSON.stringify(selectedOllamaModels))
    
    // Dispatch event to notify model selector to refresh
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('ollama-models-updated', {
        detail: { selectedModels: selectedOllamaModels }
      }))
    }
    
    toast({
      title: "Success",
      description: "Ollama model settings saved"
    })
  }

  // Toggle Ollama model selection
  const toggleOllamaModel = (modelName: string) => {
    setSelectedOllamaModels(prev => {
      if (prev.includes(modelName)) {
        return prev.filter(m => m !== modelName)
      } else {
        return [...prev, modelName]
      }
    })
  }

  // Save embeddings settings
  const saveEmbeddingsSettings = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Save embeddings provider to localStorage
    localStorage.setItem("embeddings_provider", embeddingsProvider);
    
    // If using NVIDIA API, also save the model
    if (embeddingsProvider === "nvidia") {
      localStorage.setItem("nvidia_embeddings_model", nvidiaEmbeddingsModel);
    }
    
    // Save to environment variables (this works in development; in production needs server-side implementation)
    process.env.EMBEDDINGS_PROVIDER = embeddingsProvider;
    
    if (embeddingsProvider === "nvidia") {
      process.env.NVIDIA_EMBEDDINGS_MODEL = nvidiaEmbeddingsModel;
    }
    
    // Reset the EmbeddingsService instance to pick up new settings
    try {
      // Import dynamically to avoid issues with circular dependencies
      import("@/lib/embeddings").then(({ EmbeddingsService }) => {
        EmbeddingsService.reset();
        console.log("EmbeddingsService reset successfully");
        
        // Dispatch a custom event to notify components that embeddings settings have changed
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('embeddings-settings-changed'));
        }
      });
    } catch (error) {
      console.error("Error resetting EmbeddingsService:", error);
    }
    
    toast({
      title: "Success",
      description: "Embeddings settings saved"
    })
  }
  
  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <button className="flex items-center justify-center gap-2 p-2 hover:bg-primary/10 rounded-full transition-colors" title="Settings">
          <Settings className="h-5 w-5 text-muted-foreground hover:text-primary transition-colors" />
        </button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto bg-background border-border">
        <DialogHeader className="pb-6 border-b border-border/10">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center">
              <Settings className="h-4 w-4 text-primary" />
            </div>
            <DialogTitle className="text-xl font-semibold text-foreground">
              Settings
            </DialogTitle>
          </div>
          <DialogDescription className="text-sm text-muted-foreground leading-relaxed">
            Configure your API keys and DB connections
          </DialogDescription>
        </DialogHeader>
        
        <div className="mt-4">
          <div className="mb-4">
            <Select value={activeTab} onValueChange={setActiveTab}>
              <SelectTrigger className="w-full border-border/60 bg-background text-foreground focus:border-primary/50 focus:ring-primary/20">
                <SelectValue placeholder="Select a category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="graph">
                  <div className="flex items-center gap-3">
                    <Database className="h-4 w-4 text-primary" />
                    <span>Graph Database</span>
                  </div>
                </SelectItem>
                <SelectItem value="vectordb">
                  <div className="flex items-center gap-3">
                    <SearchIcon className="h-4 w-4 text-primary" />
                    <span>Vector Database</span>
                  </div>
                </SelectItem>
                <SelectItem value="embeddings">
                  <div className="flex items-center gap-3">
                    <Cpu className="h-4 w-4 text-primary" />
                    <span>Embeddings</span>
                  </div>
                </SelectItem>
                <SelectItem value="models">
                  <div className="flex items-center gap-3">
                    <Server className="h-4 w-4 text-primary" />
                    <span>Model Management</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          

          {activeTab === "graph" && (
            <div className="bg-muted/30 border border-border/40 rounded-xl p-4">
              <form onSubmit={saveDbSettings} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <Database className="h-4 w-4 text-primary" />
                    Database Type
                  </label>
                  <select
                    value="arangodb"
                    disabled
                    className="w-full bg-background border border-border/60 rounded-md p-2 text-sm text-foreground"
                  >
                    <option value="arangodb">ArangoDB</option>
                  </select>
                </div>
              
                {true && (
                  <div className="bg-background/50 rounded-lg p-3 space-y-3">
                    <h4 className="text-sm font-medium text-foreground mb-2">ArangoDB Configuration</h4>
                    <div className="grid grid-cols-1 gap-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs font-medium text-muted-foreground mb-1 block">Connection URL</label>
                          <input
                            type="text"
                            value={arangoUrl}
                            onChange={(e) => setArangoUrl(e.target.value)}
                            placeholder="http://localhost:8529"
                            className="w-full bg-background border border-border/60 rounded-md p-2 text-sm text-foreground focus:ring-1 focus:ring-primary/50 focus:border-primary transition-colors"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-muted-foreground mb-1 block">Database Name</label>
                          <input
                            type="text"
                            value={arangoDb}
                            onChange={(e) => setArangoDb(e.target.value)}
                            placeholder="project_vyasa"
                            className="w-full bg-background border border-border/60 rounded-md p-2 text-sm text-foreground focus:ring-1 focus:ring-primary/50 focus:border-primary transition-colors"
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs font-medium text-muted-foreground mb-1 block">Username</label>
                          <input
                            type="text"
                            value={arangoUser}
                            onChange={(e) => setArangoUser(e.target.value)}
                            placeholder="root"
                            className="w-full bg-background border border-border/60 rounded-md p-2 text-sm text-foreground focus:ring-1 focus:ring-primary/50 focus:border-primary transition-colors"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-muted-foreground mb-1 block">Password</label>
                          <div className="relative">
                            <input
                              type={showPassword ? "text" : "password"}
                              value={arangoPassword}
                              onChange={(e) => setArangoPassword(e.target.value)}
                              placeholder="password"
                              className="w-full bg-background border border-border/60 rounded-md p-2 pr-8 text-sm text-foreground focus:ring-1 focus:ring-primary/50 focus:border-primary transition-colors"
                            />
                            <button
                              type="button"
                              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                              onClick={() => setShowPassword(!showPassword)}
                            >
                              {showPassword ? (
                                <EyeOff className="h-3 w-3" />
                              ) : (
                                <Eye className="h-3 w-3" />
                              )}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              
                <div className="flex justify-end pt-3 border-t border-border/30">
                  <button 
                    type="submit" 
                    className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary hover:bg-primary/90 text-white transition-colors text-sm font-medium shadow-sm"
                  >
                    <Save className="h-4 w-4" />
                    Save Settings
                  </button>
                </div>
              </form>
            </div>
          )}
          
          {activeTab === "vectordb" && (
            <div className="bg-muted/30 border border-border/40 rounded-xl p-4">
              <form onSubmit={saveVectorDbSettings} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <SearchIcon className="h-4 w-4 text-primary" />
                    Vector DB Status
                  </label>
                  <p className="text-xs text-muted-foreground">
                    Qdrant runs locally in Docker. No API keys required.
                  </p>
                </div>
                
                <div className="bg-background/50 rounded-lg p-3 space-y-3">
                  <div className="text-sm text-muted-foreground">
                    <p>Qdrant is configured via Docker Compose and environment variables.</p>
                    <p className="mt-2">Service URL: <code className="text-xs bg-muted px-1 rounded">http://vyasa-qdrant:6333</code></p>
                    <p className="mt-1">Collections: <code className="text-xs bg-muted px-1 rounded">document-embeddings</code>, <code className="text-xs bg-muted px-1 rounded">entity-embeddings</code></p>
                  </div>
                  {/* Legacy fields kept for backward compatibility but hidden */}
                  <div className="hidden">
                    <div className="grid grid-cols-1 gap-3">
                      <div>
                        <label className="text-xs font-medium text-muted-foreground mb-1 block">API Key</label>
                        <input
                          type="password"
                          value={qdrantApiKey}
                          onChange={(e) => setQdrantApiKey(e.target.value)}
                          placeholder="Not used for Qdrant"
                          className="w-full bg-background border border-border/60 rounded-md p-2 text-sm text-foreground focus:ring-1 focus:ring-primary/50 focus:border-primary transition-colors"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs font-medium text-muted-foreground mb-1 block">Environment</label>
                          <input
                            type="text"
                            value={qdrantEnvironment}
                            onChange={(e) => setQdrantEnvironment(e.target.value)}
                            placeholder="Not used for Qdrant"
                            className="w-full bg-background border border-border/60 rounded-md p-2 text-sm text-foreground focus:ring-1 focus:ring-primary/50 focus:border-primary transition-colors"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-medium text-muted-foreground mb-1 block">Index Name</label>
                          <input
                            type="text"
                            value={qdrantIndex}
                            onChange={(e) => setQdrantIndex(e.target.value)}
                            placeholder="Not used for Qdrant"
                            className="w-full bg-background border border-border/60 rounded-md p-2 text-sm text-foreground focus:ring-1 focus:ring-primary/50 focus:border-primary transition-colors"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="flex justify-end pt-3 border-t border-border/30">
                  <button 
                    type="submit" 
                    className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground transition-colors text-sm font-medium shadow-sm"
                  >
                    <Save className="h-4 w-4" />
                    Save Settings
                  </button>
                </div>
              </form>
            </div>
          )}
          
          {activeTab === "embeddings" && (
            <div className="bg-muted/30 border border-border/40 rounded-xl p-4">
              <form onSubmit={saveEmbeddingsSettings} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <Cpu className="h-4 w-4 text-primary" />
                    Embeddings Provider
                  </label>
                </div>
                
                <div className="bg-background/50 rounded-lg p-3 space-y-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">Provider Type</label>
                    <select
                      value={embeddingsProvider}
                      onChange={(e) => setEmbeddingsProvider(e.target.value)}
                      className="w-full bg-background border border-border/60 rounded-md p-2 text-sm text-foreground focus:ring-1 focus:ring-primary/50 focus:border-primary transition-colors"
                    >
                      <option value="local">Local Sentence Transformer</option>
                      <option value="nvidia">NVIDIA API</option>
                    </select>
                  </div>
                  
                  {embeddingsProvider === "nvidia" && (
                    <div className="space-y-3 pt-3 border-t border-border/30">
                      <div>
                        <label className="text-xs font-medium text-muted-foreground mb-1 block">Model Name</label>
                        <input
                          type="text"
                          value={nvidiaEmbeddingsModel}
                          onChange={(e) => setNvidiaEmbeddingsModel(e.target.value)}
                          placeholder="nvidia/llama-3.2-nv-embedqa-1b-v2"
                          className="w-full bg-background border border-border/60 rounded-md p-2 text-sm text-foreground focus:ring-1 focus:ring-primary/50 focus:border-primary transition-colors"
                        />
                      </div>
                      
                      <div className="bg-amber-50 border border-amber-200 rounded-md p-2">
                        <p className="text-xs text-amber-800 flex items-start gap-2">
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3 mt-0.5 flex-shrink-0 text-amber-600">
                            <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
                          </svg>
                          NVIDIA API key is configured via environment variables
                        </p>
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="flex justify-end pt-3 border-t border-border/30">
                  <button 
                    type="submit" 
                    className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground transition-colors text-sm font-medium shadow-sm"
                  >
                    <Save className="h-4 w-4" />
                    Save Settings
                  </button>
                </div>
              </form>
            </div>
          )}
          
          {activeTab === "models" && (
            <div className="bg-muted/30 border border-border/40 rounded-xl p-4">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <label className="text-sm font-semibold text-foreground flex items-center gap-2">
                      <Server className="h-4 w-4 text-primary" />
                      Ollama Model Configuration
                    </label>
                    <p className="text-xs text-muted-foreground">
                      Select models for triple extraction dropdown
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={fetchOllamaModels}
                    disabled={isLoadingOllamaModels}
                    className="flex items-center gap-2 px-3 py-1.5 text-xs bg-secondary hover:bg-secondary/80 text-secondary-foreground rounded-md transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <RefreshCw className={`h-3 w-3 ${isLoadingOllamaModels ? 'animate-spin' : ''}`} />
                    {isLoadingOllamaModels ? 'Loading...' : 'Refresh'}
                  </button>
                </div>

                {ollamaConnectionStatus === 'error' && ollamaError && (
                  <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-destructive text-xs">
                      <X className="h-3 w-3 flex-shrink-0" />
                      <span className="font-medium">Connection Error</span>
                    </div>
                    <p className="text-xs text-destructive/90 mt-1">{ollamaError}</p>
                  </div>
                )}

                {ollamaConnectionStatus === 'connected' && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-green-800 text-xs">
                      <Check className="h-3 w-3 flex-shrink-0" />
                      <span className="font-medium">Connected</span>
                      <span className="text-green-700">
                        • {availableOllamaModels.length} model{availableOllamaModels.length !== 1 ? 's' : ''} found
                      </span>
                    </div>
                  </div>
                )}

                {availableOllamaModels.length > 0 && (
                  <div className="bg-background/50 rounded-lg p-3 space-y-3">
                    <form onSubmit={saveOllamaSettings} className="space-y-3">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <label className="text-xs font-medium text-muted-foreground">Available Models</label>
                          <span className="text-xs text-muted-foreground">
                            {selectedOllamaModels.length} of {availableOllamaModels.length} selected
                          </span>
                        </div>
                        <div className="grid gap-1 max-h-48 overflow-y-auto border border-border/60 rounded-md p-2 bg-background">
                          {availableOllamaModels.map((model) => (
                            <label
                              key={model}
                              className="flex items-center gap-2 p-2 rounded hover:bg-muted/50 cursor-pointer transition-colors text-sm"
                            >
                              <input
                                type="checkbox"
                                checked={selectedOllamaModels.includes(model)}
                                onChange={() => toggleOllamaModel(model)}
                                className="h-3 w-3 rounded border-input text-primary focus:ring-1 focus:ring-primary/50"
                              />
                              <Server className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                              <span className="text-xs font-medium text-foreground truncate">{model}</span>
                            </label>
                          ))}
                        </div>
                      </div>

                      <div className="flex justify-between items-center pt-2 border-t border-border/30">
                        <div className="flex gap-2 text-xs">
                          <button
                            type="button"
                            onClick={() => setSelectedOllamaModels(availableOllamaModels)}
                            className="text-primary hover:text-primary/80 transition-colors font-medium"
                          >
                            All
                          </button>
                          <span className="text-muted-foreground/50">|</span>
                          <button
                            type="button"
                            onClick={() => setSelectedOllamaModels([])}
                            className="text-primary hover:text-primary/80 transition-colors font-medium"
                          >
                            None
                          </button>
                        </div>
                        <button 
                          type="submit" 
                          className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground transition-colors text-xs font-medium shadow-sm"
                        >
                          <Save className="h-3 w-3" />
                          Save Settings
                        </button>
                      </div>
                    </form>
                  </div>
                )}

                {availableOllamaModels.length === 0 && ollamaConnectionStatus === 'idle' && (
                  <div className="text-center py-8 bg-muted/20 rounded-lg border border-border/30">
                    <Server className="h-8 w-8 mx-auto text-muted-foreground/50 mb-2" />
                    <p className="text-xs text-muted-foreground">
                      Click "Refresh" to load available models
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
} 
