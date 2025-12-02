import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { RegisterBody, RegisterResult } from "../../interfaces";

export const regApi = createApi({
  reducerPath: "register",
  baseQuery: fetchBaseQuery({
    baseUrl: "http://localhost:8000/users",
  }),
  endpoints: build => ({
    register: build.mutation<RegisterResult, RegisterBody>({
      query: credentials => {
        const rightCredentials = {
          email: credentials.email,
          password: credentials.password,
          full_name: credentials.fullName,
          home_adress: credentials.homeAddress,
        };

        return {
          url: "/reg",
          method: "POST",
          body: rightCredentials,
        };
      },
    }),
  }),
});

export const { useRegisterMutation } = regApi;
