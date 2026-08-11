import { Routes, Route, Navigate } from 'react-router-dom'
import Landing from '../pages/Landing'
import Login from '../pages/Login'
import Signup from '../pages/Signup'
import Dashboard from '../pages/Dashboard'
import Domains from '../pages/Domains'
import Install from '../pages/Install'
import Brand from '../pages/Brand'
import Previews from '../pages/Previews'
import Analytics from '../pages/Analytics'
import Billing from '../pages/Billing'
import Activity from '../pages/Activity'
import ProtectedRoute from './ProtectedRoute'
import PaidRoute from './PaidRoute'
import AdminRoute from './AdminRoute'
import AdminDashboard from '../pages/admin/AdminDashboard'
import AdminUsers from '../pages/admin/AdminUsers'
import AdminDomains from '../pages/admin/AdminDomains'
import AdminPreviews from '../pages/admin/AdminPreviews'
import AdminSystem from '../pages/admin/AdminSystem'
import AdminActivity from '../pages/admin/AdminActivity'
import AdminAnalytics from '../pages/admin/AdminAnalytics'
import AdminErrors from '../pages/admin/AdminErrors'
import AdminBlog from '../pages/admin/AdminBlog'
import AdminBlogEditor from '../pages/admin/AdminBlogEditor'
import AdminBlogCategories from '../pages/admin/AdminBlogCategories'
import AdminNewsletter from '../pages/admin/AdminNewsletter'
import Organizations from '../pages/Organizations'
import OrganizationMembers from '../pages/OrganizationMembers'
import OrganizationSettings from '../pages/OrganizationSettings'
import JoinOrganization from '../pages/JoinOrganization'
import AccountSettings from '../pages/AccountSettings'
import Blog from '../pages/Blog'
import BlogPost from '../pages/BlogPost'
import Demo from '../pages/Demo'
import ForgotPassword from '../pages/ForgotPassword'
import ResetPassword from '../pages/ResetPassword'
import Terms from '../pages/legal/Terms'
import Privacy from '../pages/legal/Privacy'
import NotFound from '../pages/NotFound'

export default function Router() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/demo" element={<Demo />} />
      
      {/* Public Blog routes */}
      <Route path="/blog" element={<Blog />} />
      <Route path="/blog/:slug" element={<BlogPost />} />

      {/* Protected routes */}
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/domains"
        element={
          <ProtectedRoute>
            <Domains />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/install"
        element={
          <ProtectedRoute>
            <Install />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/brand"
        element={
          <ProtectedRoute>
            <Brand />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/previews"
        element={
          <ProtectedRoute>
            <PaidRoute>
              <Previews />
            </PaidRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/analytics"
        element={
          <ProtectedRoute>
            <PaidRoute>
              <Analytics />
            </PaidRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/billing"
        element={
          <ProtectedRoute>
            <Billing />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/account"
        element={
          <ProtectedRoute>
            <AccountSettings />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/activity"
        element={
          <ProtectedRoute>
            <Activity />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/organizations"
        element={
          <ProtectedRoute>
            <Organizations />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/organizations/:orgId/members"
        element={
          <ProtectedRoute>
            <OrganizationMembers />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/organizations/:orgId"
        element={
          <ProtectedRoute>
            <OrganizationSettings />
          </ProtectedRoute>
        }
      />
      <Route
        path="/join"
        element={
          <ProtectedRoute>
            <JoinOrganization />
          </ProtectedRoute>
        }
      />

      {/* Admin routes */}
      <Route
        path="/app/admin"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminDashboard />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/users"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminUsers />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/domains"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminDomains />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/previews"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminPreviews />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/system"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminSystem />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/activity"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminActivity />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/analytics"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminAnalytics />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/errors"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminErrors />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/blog"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminBlog />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/blog/new"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminBlogEditor />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/blog/categories"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminBlogCategories />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/blog/:postId"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminBlogEditor />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin/newsletter"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminNewsletter />
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      {/* Retired: the white-label site/blog builder. Blogging is an admin-only
          surface (MyMetaView's own blog); for customers, "their site" means the
          brand identity that feeds preview generation. Old links land there. */}
      <Route path="/app/sites/*" element={<Navigate to="/app/brand" replace />} />
      {/* Retired: the orphaned second demo implementation. */}
      <Route path="/demo-generation" element={<Navigate to="/demo" replace />} />

      {/* An honest 404 beats silently teleporting people to the homepage. */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

