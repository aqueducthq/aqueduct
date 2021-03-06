import Box from '@mui/material/Box';
import React from 'react';

import UserProfile from '../../utils/auth';
import MenuSidebar from './menuSidebar';

export type LayoutType = 'page' | 'workspace';

export const MenuSidebarOffset = '250px';

type Props = {
  user: UserProfile;
  children: React.ReactElement | React.ReactElement[];
  layoutType?: LayoutType;
};

export const DefaultLayout: React.FC<Props> = ({
  user,
  children,
  layoutType = 'page',
}) => {
  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        position: 'fixed',
        overflow: 'auto',
      }}
    >
      <Box sx={{ width: '100%', height: '100%', display: 'flex', flex: 1 }}>
        <MenuSidebar user={user} />

        {/* The margin here is fixed to be a constant (50px) more than the sidebar, which is a fixed width (200px). */}
        <Box
          sx={{
            marginLeft: MenuSidebarOffset,
            marginRight: layoutType === 'page' ? MenuSidebarOffset : '0px',
            width: '100%',
            marginTop: 3,
          }}
        >
          {children}
        </Box>
      </Box>
    </Box>
  );
};

export default DefaultLayout;
