import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { HomePage, DataPage, IntegrationsPage, IntegrationDetailsPage, WorkflowPage, WorkflowsPage, LoginPage, AccountPage } from '@aqueducthq/common';
import { store } from './stores/store';
import { Provider } from 'react-redux';
import { useUser, UserProfile } from '@aqueducthq/common';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { theme } from '@aqueducthq/common/src/styles/theme/theme';
import { getPathPrefix } from '@aqueducthq/common/src/utils/getPathPrefix';
import '@aqueducthq/common/src/styles/globals.css';

function RequireAuth({ children, user }): { children: JSX.Element, user: UserProfile | undefined } {
  const pathPrefix = getPathPrefix();
  let routesContent: React.ReactElement;

  if (!user || !user.apiKey) {
    return <Navigate to={`${pathPrefix}/login`} replace />;
  }

  return children;
}

const App = () => {
  const { user, loading } = useUser();
  if (loading) {
    return null;
  }

  const pathPrefix = getPathPrefix();
  let routesContent: React.ReactElement;
  routesContent = (
    <Routes>
      <Route path={`${ pathPrefix ?? "/" }`} element={<RequireAuth user={user}><HomePage user={user} /> </RequireAuth>} />
      <Route path={`/${pathPrefix}/data`} element={<RequireAuth user={user}><DataPage user={user} /> </RequireAuth>} />
      <Route path={`/${pathPrefix}/integrations`} element={<RequireAuth user={user}><IntegrationsPage user={user} /> </RequireAuth>} />
      <Route path={`/${pathPrefix}/integration/:id`} element={<RequireAuth user={user}><IntegrationDetailsPage user={user} /> </RequireAuth>} />
      <Route path={`/${pathPrefix}/workflows`} element={<RequireAuth user={user}><WorkflowsPage user={user} /> </RequireAuth>} />
      <Route path={`/${pathPrefix}/login`} element={ user && user.apiKey ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path={`/${pathPrefix}/account`} element={<RequireAuth user={user}><AccountPage user={user} /> </RequireAuth>} />
      <Route path={`/${pathPrefix}/workflow/:id`} element={<RequireAuth user={user}><WorkflowPage user={user} /> </RequireAuth>} />
    </Routes>
  );

  const muiTheme = createTheme(theme);
  return (
      <ThemeProvider theme={muiTheme}>
        <BrowserRouter>{routesContent}</BrowserRouter>
      </ThemeProvider>
  );
};


const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <Provider store={store}>
      <App />
    </Provider>
  </React.StrictMode>
)
