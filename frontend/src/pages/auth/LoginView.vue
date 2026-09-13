<template>
  <form
    class="grow mx-auto w-3/5 lg:w-2/5 h-screen flex flex-col justify-center gap-4"
    @submit.prevent="onSubmit"
  >
    <h3 class="mb-4 text-center text-2xl font-medium text-gray-800 tracking-tight">
      Login
    </h3>
    <Input
      v-model="email"
      placeholder="Email"
    />
    <Input
      v-model="password"
      type="password"
      placeholder="Password"
    />
    <Button :disabled="loading">
      {{ loading ? "Logging in…" : "Log In" }}
    </Button>
    <Alert
      v-if="error"
      variant="destructive"
    >
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        {{ error }}
      </AlertDescription>
    </Alert>
  </form>
</template>

<script setup lang="ts">
import {ref} from "vue";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import {storeToRefs} from "pinia";
import {Alert, AlertDescription, AlertTitle} from "@/components/ui/alert";

const authStore = useAuthStore();
const {loading, error} = storeToRefs(authStore);
const {login} = authStore;
const email = ref("");
const password = ref("");

const onSubmit = () => {
  login(email.value, password.value);
};
</script>
