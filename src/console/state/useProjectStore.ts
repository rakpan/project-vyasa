/**
 * Zustand store for Project Kernel state management.
 * Manages active project, project list, and loading states.
 * Persists activeProjectId to localStorage for context restoration.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ProjectConfig, ProjectSummary, ProjectCreate } from '@/types/project';
import * as projectService from '@/services/projectService';
import { ApiError } from '@/lib/api';

interface ProjectState {
  // State
  activeProjectId: string | null;
  projects: ProjectSummary[];
  activeProject: ProjectConfig | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchProjects: () => Promise<void>;
  setActiveProject: (id: string) => Promise<void>;
  createProject: (payload: ProjectCreate) => Promise<ProjectConfig>;
  clearActiveProject: () => void;
  clearError: () => void;
}

export const useProjectStore = create<ProjectState>()(
  persist(
    (set, get) => ({
      // Initial state
      activeProjectId: null,
      projects: [],
      activeProject: null,
      isLoading: false,
      error: null,

      /**
       * Fetch all projects and update the projects list.
       */
      fetchProjects: async () => {
        set({ isLoading: true, error: null });
        try {
          const projects = await projectService.listProjects();
          set({ projects, isLoading: false });
        } catch (error) {
          const message = projectService.safeParseError(error);
          set({ error: message, isLoading: false });
          console.error('Failed to fetch projects:', error);
        }
      },

      /**
       * Set the active project by ID and fetch full details.
       * If the project is already loaded and matches the ID, no fetch occurs.
       */
      setActiveProject: async (id: string) => {
        // If already active and loaded, no-op
        const current = get();
        if (current.activeProjectId === id && current.activeProject?.id === id) {
          return;
        }

        set({ activeProjectId: id, isLoading: true, error: null, activeProject: null });
        
        try {
          const project = await projectService.getProject(id);
          set({ activeProject: project, isLoading: false });
        } catch (error) {
          const message = projectService.safeParseError(error);
          set({ 
            error: message, 
            isLoading: false,
            activeProject: null,
            // Clear activeProjectId if project not found
            activeProjectId: error instanceof ApiError && error.status === 404 
              ? null 
              : get().activeProjectId,
          });
          console.error(`Failed to fetch project ${id}:`, error);
        }
      },

      /**
       * Create a new project, refresh the list, and set it as active.
       */
      createProject: async (payload: ProjectCreate) => {
        set({ isLoading: true, error: null });
        
        try {
          const newProject = await projectService.createProject(payload);
          
          // Refresh projects list
          const projects = await projectService.listProjects();
          
          // Set new project as active
          set({
            projects,
            activeProject: newProject,
            activeProjectId: newProject.id,
            isLoading: false,
          });
          
          return newProject;
        } catch (error) {
          const message = projectService.safeParseError(error);
          set({ error: message, isLoading: false });
          console.error('Failed to create project:', error);
          throw error;
        }
      },

      /**
       * Clear the active project (does not clear projects list).
       */
      clearActiveProject: () => {
        set({ activeProjectId: null, activeProject: null });
      },

      /**
       * Clear the error state.
       */
      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'project-vyasa-active-project', // localStorage key
      // Only persist activeProjectId (not full project data or list)
      partialize: (state) => ({
        activeProjectId: state.activeProjectId,
      }),
      // On rehydrate, fetch the active project if ID exists
      onRehydrateStorage: () => (state) => {
        if (state?.activeProjectId) {
          // Fetch the full project details
          state.setActiveProject(state.activeProjectId).catch((error) => {
            console.error('Failed to rehydrate active project:', error);
          });
        }
      },
    }
  )
);

