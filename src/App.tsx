import "./App.scss";
import { useAppDispatch, useAppSelector, useCheckAuth } from "./app/hooks";
import { Login } from "./features/Login/Login";
import { Home } from "./features/Home/Home";
import {
  selectAuthLoading,
  selectToken,
  selectUser,
} from "./features/Login/LoginSlice";
import { addNotification } from "./features/ui/Notification/NotificationSlice";
import { useEffect, type JSX } from "react";
import { transactionsApi } from "./features/Transaction/TransactionApi";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  Outlet,
  useLocation,
} from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";

import { Reg } from "./features/Register/Reg";
import { type Transaction } from "./interfaces";

const PrivateRoutes = (props: { condition: boolean }) => {
  return props.condition ? <Outlet /> : <Navigate to="/login" />;
};

export const PublicRoute = (props: { condition: boolean }) => {
  return props.condition ? <Navigate to="/home" /> : <Outlet />;
};

const PageWrapper = ({ children }: { children: React.ReactNode }) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.95 }}
    animate={{ opacity: 1, scale: 1 }}
    exit={{ opacity: 0, scale: 0.95 }}
    transition={{ duration: 0.3, ease: "easeInOut" }}
    className="page"
    style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      minHeight: "100vh",
    }}
  >
    {children}
  </motion.div>
);

export const AnimatedRoutes = (): JSX.Element => {
  const location = useLocation();
  const isLogged = useAppSelector(selectToken);
  const user = useAppSelector(selectUser);

  return (
    <AnimatePresence mode="wait">
      <Routes key={location.pathname} location={location}>
        <Route
          element={<PrivateRoutes condition={Boolean(user && isLogged)} />}
        >
          <Route
            path="/home"
            element={
              <PageWrapper>
                <Home />
              </PageWrapper>
            }
          />
        </Route>

        <Route element={<PublicRoute condition={Boolean(user && isLogged)} />}>
          <Route path="/login" element={<Login />} />
          <Route
            path="/reg"
            element={
              <PageWrapper>
                <Reg />
              </PageWrapper>
            }
          />
        </Route>

        <Route path="*" element={<Navigate to="/home" />} />
      </Routes>
    </AnimatePresence>
  );
};

export const App = (): JSX.Element => {
  const dispatch = useAppDispatch();
  const isLogged = useAppSelector(selectToken);
  const user = useAppSelector(selectUser);
  const authLoading = useAppSelector(selectAuthLoading);

  useCheckAuth();

  useEffect(() => {
    if (isLogged && user) {
      const sse = new EventSource("http://localhost:8000/transactions/sse");
      sse.onmessage = message => {
        const data: string = message.data as string;
        dispatch(transactionsApi.util.invalidateTags(["Transaction"]));
        if (data.includes("Deleted")) {
          const transactionData = JSON.parse(
            data.split(": ").slice(1).join(""),
          ) as Transaction;
          dispatch(
            addNotification({
              id: transactionData.id,
              shop_name: transactionData.shop_name,
            }),
          );
        }
      };
      return () => {
        sse.close();
      };
    }
  }, [isLogged, user, dispatch]);

  if (authLoading) return <div className="loader">Загрузка</div>;

  return (
    <div className="App">
      <BrowserRouter>
        <AnimatedRoutes />
      </BrowserRouter>
    </div>
  );
};
