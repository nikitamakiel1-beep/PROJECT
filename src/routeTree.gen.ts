/* eslint-disable */
// @ts-nocheck
import { Route as rootRouteImport } from './routes/__root'
import { Route as IndexRouteImport } from './routes/index'
import { Route as RuntimeDiagnosticsRouteImport } from './routes/runtime-diagnostics'

const IndexRoute = IndexRouteImport.update({ id: '/', path: '/', getParentRoute: () => rootRouteImport } as any)
const RuntimeDiagnosticsRoute = RuntimeDiagnosticsRouteImport.update({ id: '/runtime-diagnostics', path: '/runtime-diagnostics', getParentRoute: () => rootRouteImport } as any)

export interface FileRoutesByFullPath {
  '/': typeof IndexRoute
  '/runtime-diagnostics': typeof RuntimeDiagnosticsRoute
}
export interface FileRoutesByTo {
  '/': typeof IndexRoute
  '/runtime-diagnostics': typeof RuntimeDiagnosticsRoute
}
export interface FileRoutesById {
  __root__: typeof rootRouteImport
  '/': typeof IndexRoute
  '/runtime-diagnostics': typeof RuntimeDiagnosticsRoute
}
export interface FileRouteTypes {
  fileRoutesByFullPath: FileRoutesByFullPath
  fullPaths: '/' | '/runtime-diagnostics'
  fileRoutesByTo: FileRoutesByTo
  to: '/' | '/runtime-diagnostics'
  id: '__root__' | '/' | '/runtime-diagnostics'
  fileRoutesById: FileRoutesById
}
export interface RootRouteChildren {
  IndexRoute: typeof IndexRoute
  RuntimeDiagnosticsRoute: typeof RuntimeDiagnosticsRoute
}
declare module '@tanstack/react-router' {
  interface FileRoutesByPath {
    '/': { id: '/'; path: '/'; fullPath: '/'; preLoaderRoute: typeof IndexRouteImport; parentRoute: typeof rootRouteImport }
    '/runtime-diagnostics': { id: '/runtime-diagnostics'; path: '/runtime-diagnostics'; fullPath: '/runtime-diagnostics'; preLoaderRoute: typeof RuntimeDiagnosticsRouteImport; parentRoute: typeof rootRouteImport }
  }
}
const rootRouteChildren: RootRouteChildren = { IndexRoute, RuntimeDiagnosticsRoute }
export const routeTree = rootRouteImport._addFileChildren(rootRouteChildren)._addFileTypes<FileRouteTypes>()
import type { getRouter } from './router.tsx'
import type { startInstance } from './start.ts'
declare module '@tanstack/react-start' {
  interface Register {
    ssr: true
    router: Awaited<ReturnType<typeof getRouter>>
    config: Awaited<ReturnType<typeof startInstance.getOptions>>
  }
}
