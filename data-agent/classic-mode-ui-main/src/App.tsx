import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/hooks/useTheme";
import AppSidebar from "@/components/AppSidebar";
import DashboardPage from "@/pages/DashboardPage";
import UploadPage from "@/pages/UploadPage";
import TablesPage from "@/pages/TablesPage";
import ViewsPage from "@/pages/ViewsPage";
import SqlPage from "@/pages/SqlPage";
import AiPage from "@/pages/AiPage";
import SettingsPage from "@/pages/SettingsPage";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <div className="flex h-screen overflow-hidden">
            <AppSidebar />
            <main className="flex-1 overflow-y-auto p-6">
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/tables" element={<TablesPage />} />
                <Route path="/views" element={<ViewsPage />} />
                <Route path="/sql" element={<SqlPage />} />
                <Route path="/ask" element={<AiPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </main>
          </div>
        </BrowserRouter>
      </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
